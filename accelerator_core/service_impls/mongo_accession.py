"""
Accession support concrete implementation for Mongo data store
"""

from bson import ObjectId

from accelerator_core.service_impls.accel_db_context import AccelDbContext
from accelerator_core.services.accel_source_ingest import IngestSourceDescriptor
from accelerator_core.services.accession import Accession
from accelerator_core.utils.accelerator_config import AcceleratorConfig
from accelerator_core.utils.logger import setup_logger

logger = setup_logger("accelerator")


class AccessionMongo(Accession):
    """
    Accession module based on Mongo persistence
    """

    def __init__(
        self, accelerator_config: AcceleratorConfig, accel_db_context: AccelDbContext
    ):
        """
        Initialize the Accession sservice
        :param accelerator_config: AcceleratorConfig with general configuration
        :param accel_db_context: AccelDbContext that holds the db connection
        """
        Accession.__init__(self, accelerator_config)
        self.accel_db_context = accel_db_context

    def validate(
        self, json_dict: dict, ingest_source_descriptor: IngestSourceDescriptor
    ) -> bool:
        return super().validate(json_dict, ingest_source_descriptor)

    def ingest(
        self,
        accel_document: dict,
        ingest_source_descriptor: IngestSourceDescriptor,
        check_duplicates: bool = True,
        temp_doc: bool = False,
    ) -> str:
        """
        Ingest the given document
        :param accel_document: dict which is the document structure
        :param ingest_source_descriptor: ingest source descriptor describing the type, schema,
        and other configuration
        :param check_duplicates: bool indicates whether pre-checks for duplicate data run
        :param temp_doc: bool indicates whether the document is temporary or not
        :return: str with id of the ingested document
        """
        logger.info("ingest()")
        valid = self.validate(accel_document, ingest_source_descriptor)
        if not valid:
            raise Exception("Invalid document provided")

        db = self.connect_to_db()
        coll = self.build_collection_reference(
            db, ingest_source_descriptor.type, temp_doc
        )

        id = coll.insert_one(accel_document).inserted_id

        logger.info(f"inserted id {id}")
        return id

    def decommission(self, document_type, document_id):
        """
        Remove a document from the temp collection
        :param document_id: unique id for the document
        :param document_type: the type of document to be decommissioned, per the type matrix
        """
        logger.info(f"decommission({document_id} of type {document_type})")

        type_matrix_info = self.accelerator_config.find_type_matrix_info_for_type(
            document_type
        )
        if not type_matrix_info:
            raise Exception(f"unknown type {document_type}")

        db = self.connect_to_db()
        coll = self.build_collection_reference(db, document_type)
        delete_result = coll.delete_one(
            {"_id": ObjectId(document_id)}
        )  # TODO:think of a trash can model
        logger.info(f"deleted id {delete_result}")

    def delete_temp_document(self, document_type: str, document_id: str):
        """
        Remove a document from the temp collection
        :param document_id:
        """
        logger.info(f"delete_temp_document({document_id})")

        db = self.connect_to_db()
        coll = self.build_collection_reference(db, document_type, temp_doc=True)
        delete_result = coll.delete_one({"_id": ObjectId(document_id)})
        logger.info(f"deleted id {delete_result}")

    def find_by_id(
        self, document_id: str, document_type: str, temp_doc: bool = False
    ) -> dict:
        """
        Find the document by id, from either the AIP store or the temporary store
        :param document_id: unique id for the document
        :param document_type type of document per type matrix
        :param temp_doc: bool indicates whether the document is temporary or not
        :return: dict with the document structure
        """

        logger.info(f"find_by_id({document_id}) is temp doc? {temp_doc}")

        db = self.connect_to_db()
        coll = self.build_collection_reference(db, document_type, temp_doc=False)
        doc = coll.find_one({"_id": ObjectId(document_id)})
        return doc

    def connect_to_db(self):
        return self.accel_db_context.db

    def build_collection_reference(
        self, db, document_type: str, temp_doc: bool = False
    ):
        """
        Find the correct collection based on the document type information in the ingest_source_descriptor
        :param db: Mongo db
        :param document_type: type of the document, per the type matrix
        :param temp_doc: bool is True if this is a temporary document
        :return: the mongo collection
        """

        type_matrix_info = self.accelerator_config.find_type_matrix_info_for_type(
            document_type
        )
        if not type_matrix_info:
            raise Exception(f"unknown type {document_type}")

        if temp_doc:
            coll_name = type_matrix_info.collection
        else:
            coll_name = type_matrix_info.temp_collection

        return db[coll_name]
