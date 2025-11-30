"""
ChromaDB Client - Vector database for PI System metadata and semantic search
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import chromadb
from chromadb.config import Settings as ChromaSettings
from loguru import logger

from app.core.config import settings


class ChromaDBClient:
    """Client for ChromaDB vector database operations"""

    def __init__(self):
        """Initialize ChromaDB client"""
        self.persist_directory = Path(settings.vector_db.persist_directory)
        self.collection_name = settings.vector_db.collection_name

        # Create persist directory if it doesn't exist
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
        )

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "PI System metadata embeddings"}
        )

        logger.info(f"ChromaDB initialized: {self.persist_directory}")
        logger.info(f"Collection '{self.collection_name}' loaded with {self.collection.count()} documents")

    def add_documents(
        self,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
    ) -> bool:
        """
        Add documents to the collection

        Args:
            documents: List of text documents
            metadatas: List of metadata dictionaries
            ids: List of unique IDs for documents

        Returns:
            True if successful
        """
        try:
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )
            logger.debug(f"Added {len(documents)} documents to collection")
            return True

        except Exception as e:
            logger.error(f"Error adding documents: {e}")
            return False

    def query(
        self,
        query_texts: List[str],
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Query the collection

        Args:
            query_texts: List of query texts
            n_results: Number of results to return
            where: Metadata filter
            where_document: Document content filter

        Returns:
            Query results
        """
        try:
            results = self.collection.query(
                query_texts=query_texts,
                n_results=n_results,
                where=where,
                where_document=where_document,
            )
            logger.debug(f"Query returned {len(results['ids'][0])} results")
            return results

        except Exception as e:
            logger.error(f"Error querying collection: {e}")
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    def search_elements(
        self,
        query: str,
        n_results: int = 10,
        element_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for PI elements using semantic search

        Args:
            query: Search query
            n_results: Number of results
            element_type: Filter by element type (e.g., "element", "attribute", "point")

        Returns:
            List of matching elements with metadata
        """
        try:
            where = None
            if element_type:
                where = {"type": element_type}

            results = self.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
            )

            # Format results
            formatted_results = []
            if results["ids"] and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    formatted_results.append({
                        "id": results["ids"][0][i],
                        "document": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i],
                    })

            return formatted_results

        except Exception as e:
            logger.error(f"Error searching elements: {e}")
            return []

    def index_element(
        self,
        element_path: str,
        element_name: str,
        element_description: str,
        element_type: str,
        attributes: Optional[List[str]] = None,
        template: Optional[str] = None,
        categories: Optional[List[str]] = None,
    ) -> bool:
        """
        Index an AF element in the vector database

        Args:
            element_path: Full path of the element
            element_name: Element name
            element_description: Element description
            element_type: Type of element
            attributes: List of attribute names
            template: Template name
            categories: List of categories

        Returns:
            True if successful
        """
        try:
            # Create searchable text
            text_parts = [element_name]
            if element_description:
                text_parts.append(element_description)
            if template:
                text_parts.append(f"Template: {template}")
            if attributes:
                text_parts.append(f"Attributes: {', '.join(attributes)}")
            if categories:
                text_parts.append(f"Categories: {', '.join(categories)}")

            document = " | ".join(text_parts)

            # Create metadata
            metadata = {
                "path": element_path,
                "name": element_name,
                "type": element_type,
                "template": template or "",
            }

            # Use path as unique ID
            doc_id = element_path.replace("\\", "_").replace("/", "_")

            return self.add_documents(
                documents=[document],
                metadatas=[metadata],
                ids=[doc_id],
            )

        except Exception as e:
            logger.error(f"Error indexing element: {e}")
            return False

    def index_pi_point(
        self,
        point_name: str,
        point_description: str,
        engineering_units: Optional[str] = None,
        point_type: Optional[str] = None,
        point_source: Optional[str] = None,
    ) -> bool:
        """
        Index a PI Point in the vector database

        Args:
            point_name: PI Point name
            point_description: Point description
            engineering_units: Engineering units
            point_type: Point type
            point_source: Point source

        Returns:
            True if successful
        """
        try:
            # Create searchable text
            text_parts = [point_name]
            if point_description:
                text_parts.append(point_description)
            if engineering_units:
                text_parts.append(f"Units: {engineering_units}")
            if point_type:
                text_parts.append(f"Type: {point_type}")
            if point_source:
                text_parts.append(f"Source: {point_source}")

            document = " | ".join(text_parts)

            # Create metadata
            metadata = {
                "name": point_name,
                "type": "pi_point",
                "units": engineering_units or "",
                "point_type": point_type or "",
            }

            # Use point name as unique ID
            doc_id = f"point_{point_name}"

            return self.add_documents(
                documents=[document],
                metadatas=[metadata],
                ids=[doc_id],
            )

        except Exception as e:
            logger.error(f"Error indexing PI Point: {e}")
            return False

    def bulk_index_elements(
        self,
        elements: List[Dict[str, Any]]
    ) -> int:
        """
        Bulk index multiple elements

        Args:
            elements: List of element dictionaries

        Returns:
            Number of successfully indexed elements
        """
        documents = []
        metadatas = []
        ids = []

        for element in elements:
            # Create searchable text
            text_parts = [element.get("name", "")]
            if element.get("description"):
                text_parts.append(element["description"])
            if element.get("template"):
                text_parts.append(f"Template: {element['template']}")

            document = " | ".join(text_parts)
            documents.append(document)

            # Create metadata
            metadata = {
                "path": element.get("path", ""),
                "name": element.get("name", ""),
                "type": element.get("type", "element"),
                "template": element.get("template", ""),
            }
            metadatas.append(metadata)

            # Create ID
            doc_id = element.get("path", "").replace("\\", "_").replace("/", "_")
            ids.append(doc_id)

        try:
            self.add_documents(documents, metadatas, ids)
            logger.success(f"Bulk indexed {len(elements)} elements")
            return len(elements)

        except Exception as e:
            logger.error(f"Error bulk indexing elements: {e}")
            return 0

    def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document from the collection

        Args:
            doc_id: Document ID

        Returns:
            True if successful
        """
        try:
            self.collection.delete(ids=[doc_id])
            logger.debug(f"Deleted document: {doc_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            return False

    def clear_collection(self) -> bool:
        """
        Clear all documents from the collection

        Returns:
            True if successful
        """
        try:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "PI System metadata embeddings"}
            )
            logger.warning("Collection cleared")
            return True

        except Exception as e:
            logger.error(f"Error clearing collection: {e}")
            return False

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get collection statistics

        Returns:
            Statistics dictionary
        """
        try:
            count = self.collection.count()
            return {
                "name": self.collection_name,
                "count": count,
                "persist_directory": str(self.persist_directory),
            }

        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {}
