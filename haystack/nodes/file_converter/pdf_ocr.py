import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pdf2image import convert_from_path
except (ImportError, ModuleNotFoundError) as ie:
    from haystack.utils.import_utils import _optional_component_not_installed

    _optional_component_not_installed(__name__, "ocr", ie)

from haystack.nodes.file_converter.base import BaseConverter
from haystack.nodes.file_converter.image import ImageToTextConverter
from haystack.schema import Document

logger = logging.getLogger(__name__)


class PDFToTextOCRConverter(BaseConverter):
    def __init__(
        self,
        remove_numeric_tables: bool = False,
        valid_languages: Optional[List[str]] = None,
        id_hash_keys: Optional[List[str]] = None,
    ):
        """
        Extract text from image file using the pytesseract library (https://github.com/madmaze/pytesseract)

        :param remove_numeric_tables: This option uses heuristics to remove numeric rows from the tables.
                                      The tabular structures in documents might be noise for the reader model if it
                                      does not have table parsing capability for finding answers. However, tables
                                      may also have long strings that could possible candidate for searching answers.
                                      The rows containing strings are thus retained in this option.
        :param valid_languages: validate languages from a list of languages supported by tessarect
                                (https://tesseract-ocr.github.io/tessdoc/Data-Files-in-different-versions.html).
                                This option can be used to add test for encoding errors. If the extracted text is
                                not one of the valid languages, then it might likely be encoding error resulting
                                in garbled text. If no value is provided, English will be set as default.
        :param id_hash_keys: Generate the document id from a custom list of strings that refer to the document's
            attributes. If you want to ensure you don't have duplicate documents in your DocumentStore but texts are
            not unique, you can modify the metadata and pass e.g. `"meta"` to this field (e.g. [`"content"`, `"meta"`]).
            In this case the id will be generated by using the content and the defined metadata.
        """
        if valid_languages is None:
            valid_languages = ["eng"]
        # init image to text instance
        self.image_2_text = ImageToTextConverter(remove_numeric_tables, valid_languages)

        super().__init__(
            remove_numeric_tables=remove_numeric_tables, valid_languages=valid_languages, id_hash_keys=id_hash_keys
        )

    def convert(
        self,
        file_path: Path,
        meta: Optional[Dict[str, Any]] = None,
        remove_numeric_tables: Optional[bool] = None,
        valid_languages: Optional[List[str]] = None,
        encoding: Optional[str] = None,
        id_hash_keys: Optional[List[str]] = None,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
    ) -> List[Document]:
        """
        Convert a file to a dictionary containing the text and any associated meta data.

        File converters may extract file meta like name or size. In addition to it, user
        supplied meta data like author, url, external IDs can be supplied as a dictionary.

        :param file_path: path of the file to convert
        :param meta: dictionary of meta data key-value pairs to append in the returned document.
        :param remove_numeric_tables: This option uses heuristics to remove numeric rows from the tables.
                                      The tabular structures in documents might be noise for the reader model if it
                                      does not have table parsing capability for finding answers. However, tables
                                      may also have long strings that could possible candidate for searching answers.
                                      The rows containing strings are thus retained in this option.
        :param valid_languages: validate languages from a list of languages specified in the ISO 639-1
                                (https://en.wikipedia.org/wiki/ISO_639-1) format.
                                This option can be used to add test for encoding errors. If the extracted text is
                                not one of the valid languages, then it might likely be encoding error resulting
                                in garbled text.
        :param encoding: Not applicable
        :param id_hash_keys: Generate the document id from a custom list of strings that refer to the document's
            attributes. If you want to ensure you don't have duplicate documents in your DocumentStore but texts are
            not unique, you can modify the metadata and pass e.g. `"meta"` to this field (e.g. [`"content"`, `"meta"`]).
            In this case the id will be generated by using the content and the defined metadata.
        :param start_page: The page number where to start the conversion
        :param end_page: The page number where to end the conversion.
        """
        if id_hash_keys is None:
            id_hash_keys = self.id_hash_keys

        start_page = start_page or 1

        pages = []
        try:
            images = convert_from_path(file_path, first_page=start_page, last_page=end_page)
            for image in images:
                temp_img = tempfile.NamedTemporaryFile(suffix=".jpeg")
                image.save(temp_img.name)
                pages.append(self.image_2_text.convert(file_path=temp_img.name)[0].content)
        except Exception as exception:
            logger.error("File %s has an error:\n%s", file_path, exception)

        raw_text = "\f" * (start_page - 1) + "\f".join(pages)  # tracking skipped pages for correct page numbering
        document = Document(content=raw_text, meta=meta, id_hash_keys=id_hash_keys)
        return [document]
