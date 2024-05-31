from __future__ import unicode_literals

__author__ = 'David Baum'

import io, logging, numpy, sys, tqdm, uuid

from django.core.files.base import ContentFile

from multiprocessing import cpu_count
from pathos.multiprocessing import ProcessingPool as Pool
from scipy.fftpack import dct
from typing import Dict, List, Optional, Tuple
from PIL import Image

from lj_common_shared_service.utils.hashing.retrieval import LJHashEvaluator

logger = logging.getLogger(__name__)
IMG_FORMATS = ['JPEG', 'PNG', 'BMP', 'MPO', 'PPM', 'TIFF', 'GIF', 'WEBP']


class LJImageHashing:
    """
        Inherits from Hashing base class and implements perceptual hashing (Implementation reference:
        http://www.hackerfactor.com/blog/index.php?/archives/432-Looks-Like-It.html).

        Offers all the functionality mentioned in hashing class.

        Example:
        ```
        # Perceptual hash for images
        from lj_common_shared_service.utils.images import LJImageHashing
        hasher = LJImageHashing()
        perceptual_hash = hasher.encode_images([<ContentFile>])

        # Finding duplicates:
        from lj_common_shared_service.utils.images import LJImageHashing
        hasher = LJImageHashing()
        encoding_map = hasher.encode_images([<ContentFile>])
        duplicates = hasher.find_duplicates(encoding_map=encoding_map, max_distance_threshold=15, scores=True)

        # Finding duplicates to return a single list of duplicates in the image collection
        from lj_common_shared_service.utils.images import LJImageHashing
        hasher = LJImageHashing()
        encoding_map = hasher.encode_images([<ContentFile>])
        files_to_remove = hasher.find_duplicates_to_remove(encoding_map=encoding_map, max_distance_threshold=15)
        ```
        """

    def __init__(self, verbose: bool = True) -> None:
        """
        Initialize perceptual hashing class.

        Args:
            verbose: Display progress bar if True else disable it. Default value is True.
        """
        self.verbose = verbose
        self.__coefficient_extract = (8, 8)
        self.target_size = (32, 32)

    def encode_images(
            self,
            image_files: List[ContentFile],
            num_enc_workers: int = cpu_count()
    ):
        """
        Generate hashes for all images from the list of the image files.
        Args:
            image_files: List of the Django image ContentFiles.
            num_enc_workers: Optional, number of cpu cores to use for multiprocessing encoding generation, set to number of CPUs in the system by default. 0 disables multiprocessing.
        Returns:
            dictionary: A dictionary that contains a mapping of filenames and corresponding 64 character hash string
                        such as {'Image1.jpg': 'hash_string1', 'Image2.jpg': 'hash_string2', ...}
        Example:
        ```
        from lj_common_shared_service.utils.images import LJImageHashing
        hasher = LJImageHashing()
        mapping = hasher.encode_images([<ContentFile>])
        ```
        """

        logger.info(f'Start: Calculating hashes...')

        for file in image_files:
            if not isinstance(file, ContentFile):
                raise TypeError("List of image_files should contain only django.core.files.base.ContentFile objects")
            if not file.name:
                file.name = uuid.uuid4().hex

        pool = Pool(processes=num_enc_workers)
        pool_imap = None
        try:
            pool_imap = pool.imap(self.load_image, image_files)
        except ValueError:
            pool.restart()
            pool_imap = pool.imap(self.load_image, image_files)

        processed_images = list(
            tqdm.tqdm(
                pool_imap,
                total=len(image_files),
                disable=self.verbose
            )
        )
        pool.close()
        pool.join()

        hash_dict = dict()
        for processed_image in processed_images:
            image_file_name = processed_image[1]
            if image_file_name:
                numpy_array = processed_image[0]
                image_hash = self._hash_func(numpy_array) if isinstance(numpy_array, numpy.ndarray) else None
                hash_dict[image_file_name] = image_hash

        logger.info(f'Finished calculating images hashes!')
        return hash_dict

    def load_image(
            self,
            image_file: ContentFile,
            grayscale: bool = True,
            img_formats: List[str] = IMG_FORMATS,
    ) -> numpy.ndarray:
        """
        Load an image given its path. Returns an array version of optionally resized and grayed image. Only allows images
        of types described by img_formats argument.
        Args:
            image_file: Django image ContentFile.
            target_size: Size to resize the input image to.
            grayscale: A boolean indicating whether to grayscale the image.
            img_formats: List of allowed image formats that can be loaded.
        """
        try:
            image_bytes = image_file.read()
            image = Image.open(io.BytesIO(image_bytes))

            # validate image format
            if image.format not in img_formats:
                logger.warning(f'Invalid image format {image.format}!')
                return None, image_file.name

            else:
                if image.mode != 'RGB':
                    # convert to RGBA first to avoid warning
                    # we ignore alpha channel if available
                    image = image.convert('RGBA').convert('RGB')
                numpy_array = self.preprocess_image(image, target_size=self.target_size, grayscale=grayscale)

                return numpy_array, image_file.name

        except Exception as e:
            logger.warning(f'Invalid image file {image_file}:\n{e}')
            return None, image_file.name

    def find_duplicates(
            self,
            encoding_map: Dict[str, str],
            max_distance_threshold: int = 10,
            scores: bool = False,
            search_method: str = 'brute_force' if not sys.platform == 'win32' else 'bktree',
            recursive: Optional[bool] = False,
            num_enc_workers: int = cpu_count(),
            num_dist_workers: int = cpu_count()
    ) -> Dict:
        """
        Find duplicates for each file. Takes in encoding dictionary in which duplicates are to
        be detected. All images with hamming distance less than or equal to the max_distance_threshold are regarded as
        duplicates. Returns dictionary containing key as filename and value as a list of duplicate file names.
        Optionally, the below the given hamming distance could be returned instead of just duplicate filenames for each
        query file.

        Args:
            encoding_map: Required,  used instead of image_dir, a dictionary containing mapping of filenames and
                          corresponding hashes.
            max_distance_threshold: Optional, hamming distance between two images below which retrieved duplicates are
                                    valid. (must be an int between 0 and 64). Default is 10.
            scores: Optional, boolean indicating whether Hamming distances are to be returned along with retrieved duplicates.
            search_method: Algorithm used to retrieve duplicates. Default is brute_force for Unix else bktree.
            recursive: Optional, find images recursively in a nested image directory structure, set to False by default.
            num_enc_workers: Optional, number of cpu cores to use for multiprocessing encoding generation, set to number of CPUs in the system by default. 0 disables multiprocessing.
            num_dist_workers: Optional, number of cpu cores to use for multiprocessing distance computation, set to number of CPUs in the system by default. 0 disables multiprocessing.

        Returns:
            duplicates dictionary: if scores is True, then a dictionary of the form {'image1.jpg': [('image1_duplicate1.jpg',
                        score), ('image1_duplicate2.jpg', score)], 'image2.jpg': [] ..}. if scores is False, then a
                        dictionary of the form {'image1.jpg': ['image1_duplicate1.jpg', 'image1_duplicate2.jpg'],
                        'image2.jpg':['image1_duplicate1.jpg',..], ..}

        Example:
        ```
        from lj_common_shared_service.utils.images import LJImageHashing
        myencoder = LJImageHashing()
        encoding_map = hasher.encode_images([<ContentFile>])
        duplicates = myencoder.find_duplicates(encoding_map=encoding_map, max_distance_threshold=15, scores=True)
        ```
        """
        self._check_hamming_distance_bounds(thresh=max_distance_threshold)
        if recursive:
            logger.warning(f'recursive parameter is irrelevant when using encodings. {SyntaxWarning}')

        logger.warning(
            f'Parameter num_enc_workers has no effect since encodings are already provided. {RuntimeWarning}')

        result = self._find_duplicates_dict(
            encoding_map=encoding_map,
            max_distance_threshold=max_distance_threshold,
            scores=scores,
            search_method=search_method,
            num_dist_workers=num_dist_workers
        )
        return result

    def find_duplicates_to_remove(
            self,
            encoding_map: Dict[str, str] = None,
            max_distance_threshold: int = 10,
            recursive: Optional[bool] = False,
            num_enc_workers: int = cpu_count(),
            num_dist_workers: int = cpu_count()
    ) -> List:
        """
        Give out a list of image file names to remove based on the hamming distance threshold. Does not
        remove the mentioned files.

        Args:
            encoding_map: Required, used instead of image_dir, a dictionary containing mapping of filenames and
                          corresponding hashes.
            max_distance_threshold: Optional, hamming distance between two images below which retrieved duplicates are
                                    valid. (must be an int between 0 and 64). Default is 10.
            recursive: Optional, find images recursively in a nested image directory structure, set to False by default.
            num_enc_workers: Optional, number of cpu cores to use for multiprocessing encoding generation, set to number of CPUs in the system by default. 0 disables multiprocessing.
            num_dist_workers: Optional, number of cpu cores to use for multiprocessing distance computation, set to number of CPUs in the system by default. 0 disables multiprocessing.

        Returns:
            duplicates: List of image file names that are found to be duplicate of me other file in the directory.

        Example:
        ```
        from lj_common_shared_service.utils.images import LJImageHashing
        myencoder = LJImageHashing()
        encoding_map = hasher.encode_images([<ContentFile>])
        duplicates = myencoder.find_duplicates(encoding_map=encoding_map,
        max_distance_threshold=15)
        ```
        """
        result = self.find_duplicates(
            encoding_map=encoding_map,
            max_distance_threshold=max_distance_threshold,
            scores=False,
            recursive=recursive,
            num_enc_workers=num_enc_workers,
            num_dist_workers=num_dist_workers
        )
        files_to_remove = self.remove_diplicate_files(result)
        return files_to_remove

    def _find_duplicates_dict(
            self,
            encoding_map: Dict[str, str],
            max_distance_threshold: int = 10,
            scores: bool = False,
            search_method: str = 'brute_force' if not sys.platform == 'win32' else 'bktree',
            num_dist_workers: int = cpu_count()
    ) -> Dict:
        """
        Take in dictionary {filename: encoded image}, detects duplicates below the given hamming distance threshold
        and returns a dictionary containing key as filename and value as a list of duplicate filenames. Optionally,
        the hamming distances could be returned instead of just duplicate filenames for each query file.

        Args:
            encoding_map: Dictionary with keys as file names and values as encoded images (hashes).
            max_distance_threshold: Hamming distance between two images below which retrieved duplicates are valid.
            scores: Boolean indicating whether hamming distance scores are to be returned along with retrieved
            duplicates.
            search_method: Algorithm used to retrieve duplicates. Default is brute_force for Unix else bktree.
            num_dist_workers: Optional, number of cpu cores to use for multiprocessing distance computation, set to number of CPUs in the system by default. 0 disables multiprocessing.

        Returns:
            if scores is True, then a dictionary of the form {'image1.jpg': [('image1_duplicate1.jpg',
            score), ('image1_duplicate2.jpg', score)], 'image2.jpg': [] ..}
            if scores is False, then a dictionary of the form {'image1.jpg': ['image1_duplicate1.jpg',
            'image1_duplicate2.jpg'], 'image2.jpg':['image1_duplicate1.jpg',..], ..}
        """
        logger.info('Start: Evaluating hamming distances for getting duplicates')

        result_set = LJHashEvaluator(
            test=encoding_map,
            queries=encoding_map,
            distance_function=self.hamming_distance,
            verbose=self.verbose,
            threshold=max_distance_threshold,
            search_method=search_method,
            num_dist_workers=num_dist_workers
        )

        logger.info('End: Evaluating hamming distances for getting duplicates')

        self.results = result_set.retrieve_results(scores=scores)
        return self.results

    def _hash_func(self, image_array: numpy.ndarray):
        hash_mat = self._hash_algo(image_array)
        return self._array_to_hash(hash_mat)

    def _hash_algo(self, image_array: numpy.ndarray):
        """
        Get perceptual hash of the input image.

        Args:
            image_array: numpy array that corresponds to the image.

        Returns:
            A string representing the perceptual hash of the image.
        """
        dct_coef = dct(dct(image_array, axis=0), axis=1)

        # retain top left 8 by 8 dct coefficients
        dct_reduced_coef = dct_coef[
                           : self.__coefficient_extract[0], : self.__coefficient_extract[1]
                           ]

        # median of coefficients excluding the DC term (0th term)
        # mean_coef_val = np.mean(np.ndarray.flatten(dct_reduced_coef)[1:])
        median_coef_val = numpy.median(numpy.ndarray.flatten(dct_reduced_coef)[1:])

        # return mask of all coefficients greater than mean of coefficients
        hash_mat = dct_reduced_coef >= median_coef_val
        return hash_mat

    @staticmethod
    def preprocess_image(
            image: numpy.ndarray or Image.Image, target_size: Tuple[int, int] = None, grayscale: bool = False
    ) -> numpy.ndarray:
        """
        Take as input an image as numpy array or Pillow format. Returns an array version of optionally resized and grayed
        image.

        Args:
            image: numpy array or a pillow image.
            target_size: Size to resize the input image to.
            grayscale: A boolean indicating whether to grayscale the image.

        Returns:
            A numpy array of the processed image.
        """
        if isinstance(image, numpy.ndarray):
            image = image.astype('uint8')
            image_pil = Image.fromarray(image)

        elif isinstance(image, Image.Image):
            image_pil = image
        else:
            raise ValueError('Input is expected to be a numpy array or a pillow object!')

        if target_size:
            image_pil = image_pil.resize(target_size, Image.LANCZOS)

        if grayscale:
            image_pil = image_pil.convert('L')

        return numpy.array(image_pil).astype('uint8')

    @staticmethod
    def remove_diplicate_files(duplicates: Dict[str, List]) -> List:
        """
        Get a list of files to remove.

        Args:
            duplicates: A dictionary with file name as key and a list of duplicate file names as value.

        Returns:
            A list of files that should be removed.
        """
        # iterate over dict_ret keys, get value for the key and delete the dict keys that are in the value list
        files_to_remove = set()

        for k, v in duplicates.items():
            tmp = [
                i[0] if isinstance(i, tuple) else i for i in v
            ]  # handle tuples (image_id, score)

            if k not in files_to_remove:
                files_to_remove.update(tmp)

        return list(files_to_remove)

    @staticmethod
    def _check_hamming_distance_bounds(thresh: int) -> None:
        """
        Check if provided threshold is valid. Raises TypeError if wrong threshold variable type is passed or a
        ValueError if an out of range value is supplied.

        Args:
            thresh: Threshold value (must be int between 0 and 64)

        Raises:
            TypeError: If wrong variable type is provided.
            ValueError: If invalid value is provided.
        """
        if not isinstance(thresh, int):
            raise TypeError('Threshold must be an int between 0 and 64')
        elif thresh < 0 or thresh > 64:
            raise ValueError('Threshold must be an int between 0 and 64')
        else:
            return None

    @staticmethod
    def _array_to_hash(hash_mat: numpy.ndarray) -> str:
        """
        Convert a matrix of binary numerals to 64 character hash.

        Args:
            hash_mat: A numpy array consisting of 0/1 values.

        Returns:
            An hexadecimal hash string.
        """
        return ''.join('%0.2x' % x for x in numpy.packbits(hash_mat))

    @staticmethod
    def hamming_distance(hash1: str, hash2: str) -> float:
        """
        Calculate the hamming distance between two hashes. If length of hashes is not 64 bits, then pads the length
        to be 64 for each hash and then calculates the hamming distance.

        Args:
            hash1: hash string
            hash2: hash string

        Returns:
            hamming_distance: Hamming distance between the two hashes.
        """
        hash1_bin = bin(int(hash1, 16))[2:].zfill(
            64
        )  # zfill ensures that len of hash is 64 and pads MSB if it is < A
        hash2_bin = bin(int(hash2, 16))[2:].zfill(64)
        return numpy.sum([i != j for i, j in zip(hash1_bin, hash2_bin)])
