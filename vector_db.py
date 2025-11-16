import chromadb
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import json
import hashlib
import time
from config import config, AF_TEMPLATE_CATEGORIES

logger = logging.getLogger(__name__)

class VectorDBManager:
    """Manages ChromaDB integration for AF elements indexing and search with improved performance"""
    
    def __init__(self):
        self._client = None
        self._collection = None
        self._last_index_time = None
        self._initialization_lock = asyncio.Lock() if asyncio._get_running_loop() else None
        self._client_initialized = False
        
    async def _get_lock(self):
        """Get or create async lock for current event loop"""
        if self._initialization_lock is None:
            self._initialization_lock = asyncio.Lock()
        return self._initialization_lock
        
    def get_client(self) -> chromadb.Client:
        """Get or create ChromaDB client with error handling"""
        if self._client is None or not self._client_initialized:
            try:
                if config.chroma.client_type == "persistent":
                    self._client = chromadb.PersistentClient(path=config.chroma.data_dir)
                elif config.chroma.client_type == "ephemeral":
                    self._client = chromadb.EphemeralClient()
                elif config.chroma.client_type == "http":
                    self._client = chromadb.HttpClient(
                        host=config.chroma.host,
                        port=config.chroma.port,
                        ssl=config.chroma.ssl
                    )
                elif config.chroma.client_type == "cloud":
                    self._client = chromadb.HttpClient(
                        ssl=config.chroma.ssl,
                        host="api.trychroma.com",
                        tenant=config.chroma.tenant,
                        database=config.chroma.database,
                        headers={'x-chroma-token': config.chroma.api_key}
                    )
                else:
                    raise ValueError(f"Unsupported client type: {config.chroma.client_type}")
                
                self._client_initialized = True
                logger.debug(f"ChromaDB client initialized: {config.chroma.client_type}")
                
            except Exception as e:
                logger.error(f"Failed to initialize ChromaDB client: {e}")
                raise
        
        return self._client
    
    async def get_collection(self):
        """Get or create collection for AF elements with async protection"""
        if self._collection is None:
            lock = await self._get_lock()
            async with lock:
                if self._collection is None:  # Double-check pattern
                    try:
                        client = self.get_client()
                        
                        # Try to get existing collection first
                        try:
                            self._collection = client.get_collection(config.chroma.collection_name)
                            logger.info(f"Retrieved existing collection: {config.chroma.collection_name}")
                        except Exception:
                            # Create new collection if it doesn't exist
                            self._collection = client.create_collection(
                                name=config.chroma.collection_name,
                                metadata={"description": "AF Elements hierarchical index"}
                            )
                            logger.info(f"Created new collection: {config.chroma.collection_name}")
                            
                    except Exception as e:
                        logger.error(f"Failed to get/create collection: {e}")
                        raise
        
        return self._collection
    
    def prepare_element_for_indexing(self, element: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
        """Prepare an AF element for vector indexing with enhanced content"""
        # Create searchable document text with better structure
        doc_parts = []
        
        # Basic element info
        name = element.get('Name', '')
        description = element.get('Description', '')
        
        doc_parts.append(f"Element Name: {name}")
        if description and description.strip():
            doc_parts.append(f"Description: {description}")
        
        # Path information - enhanced processing
        path = element.get('Path', '')
        if path:
            # Extract path components for better search
            path_parts = [p.strip() for p in path.split('\\') if p.strip()]
            doc_parts.append(f"Full Path: {path}")
            
            # Skip server and database parts, keep all business-relevant components
            # Typical structure: ['', 'SERVER', 'DATABASE', 'Area', 'Unit', 'Equipment', ...]
            if len(path_parts) > 2:
                business_path_parts = path_parts[2:]  # Skip server and database
                if business_path_parts:
                    doc_parts.append(f"Business Hierarchy: {' > '.join(business_path_parts)}")
                    doc_parts.append(f"Location Path: {' '.join(business_path_parts)}")
                    
                    # Add individual path components for better matching
                    for i, part in enumerate(business_path_parts):
                        level_name = ["Area", "Unit", "Equipment", "Component", "Item"][min(i, 4)]
                        doc_parts.append(f"{level_name}: {part}")
        
        # Template information with category mapping
        template_name = element.get('TemplateName', '')
        if template_name and template_name.strip():
            doc_parts.append(f"Template: {template_name}")
            # Add template category if known
            if template_name in AF_TEMPLATE_CATEGORIES:
                category = AF_TEMPLATE_CATEGORIES[template_name]
                doc_parts.append(f"Equipment Category: {category}")
                doc_parts.append(f"Type: {category}")
        
        # Add element type information
        if element.get('HasChildren', False):
            doc_parts.append("Element Type: Container")
            doc_parts.append("Has Sub-elements: Yes")
        else:
            doc_parts.append("Element Type: Leaf Node")
            doc_parts.append("Has Sub-elements: No")
        
        # Join all parts with proper spacing
        document_text = "\n".join(doc_parts)
        
        # Create comprehensive metadata
        metadata = {
            "webid": element.get('WebId', ''),
            "element_id": element.get('Id', ''),
            "name": name,
            "path": path,
            "template_name": template_name,
            "has_children": element.get('HasChildren', False),
            "indexed_at": datetime.now().isoformat(),
            "element_type": "af_element"
        }
        
        # Add template category to metadata
        if template_name and template_name in AF_TEMPLATE_CATEGORIES:
            metadata["template_category"] = AF_TEMPLATE_CATEGORIES[template_name]
        
        # Add enhanced path level information
        if path:
            path_parts = [p.strip() for p in path.split('\\') if p.strip()]
            total_path_level = len(path_parts)
            
            # Business path level (excluding server and database)
            business_path_level = max(0, total_path_level - 2)
            metadata["path_level"] = total_path_level
            metadata["business_path_level"] = business_path_level
            
            # Extract and store business hierarchy components
            if len(path_parts) > 2:
                business_components = path_parts[2:]
                metadata["business_hierarchy"] = " > ".join(business_components)
                metadata["leaf_element"] = business_components[-1] if business_components else ""
                
                # Store individual hierarchy levels for filtering
                hierarchy_levels = ["area", "unit", "equipment", "component", "item"]
                for i, component in enumerate(business_components[:5]):
                    level_key = f"hierarchy_{hierarchy_levels[i]}"
                    metadata[level_key] = component
                
                # Store parent information
                if len(business_components) >= 1:
                    metadata["parent_area"] = business_components[0]
                if len(business_components) >= 2:
                    metadata["equipment_unit"] = business_components[1]
                if len(business_components) >= 3:
                    metadata["equipment_name"] = business_components[2]
        
        # Add searchable keywords
        keywords = []
        if name:
            keywords.append(name.lower())
        if template_name:
            keywords.append(template_name.lower())
        if description:
            # Extract meaningful words from description
            desc_words = [w.strip().lower() for w in description.split() if len(w.strip()) > 2]
            keywords.extend(desc_words[:5])  # Limit to first 5 words
        
        metadata["keywords"] = " ".join(keywords)
        
        # Create unique ID with better collision avoidance
        element_id = f"af_element_{element.get('WebId', element.get('Id', str(hash(path))))}"
        
        return document_text, element_id, metadata
    
    async def index_af_elements(self, elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Index AF elements in ChromaDB with improved batch processing and error handling"""
        start_time = time.time()
        
        try:
            collection = await self.get_collection()
            
            if not elements:
                logger.warning("No elements provided for indexing")
                return {"success": False, "error": "No elements provided", "indexed_count": 0}
            
            logger.info(f"Starting indexing of {len(elements)} AF elements")
            
            # Clear existing elements to avoid duplicates
            try:
                collection.delete(where={"element_type": "af_element"})
                logger.info("Cleared existing AF elements from collection")
            except Exception as e:
                logger.warning(f"Could not clear existing elements: {e}")
            
            # Prepare all elements for indexing
            documents = []
            metadatas = []
            ids = []
            
            processed_count = 0
            skipped_count = 0
            
            for i, element in enumerate(elements):
                try:
                    doc_text, element_id, metadata = self.prepare_element_for_indexing(element)
                    
                    # Skip elements with empty names or paths
                    if not element.get('Name') or not element.get('Path'):
                        skipped_count += 1
                        continue
                    
                    documents.append(doc_text)
                    metadatas.append(metadata)
                    ids.append(element_id)
                    processed_count += 1
                    
                    # Progress logging every 50 elements
                    if (i + 1) % 50 == 0:
                        logger.info(f"Prepared {i + 1}/{len(elements)} elements for indexing")
                        # Allow other async tasks to run
                        await asyncio.sleep(0.01)
                        
                except Exception as e:
                    logger.warning(f"Error preparing element {i}: {e}")
                    skipped_count += 1
                    continue
            
            if not documents:
                return {
                    "success": False,
                    "error": "No valid elements to index",
                    "indexed_count": 0,
                    "skipped_count": skipped_count
                }
            
            logger.info(f"Prepared {processed_count} elements, skipped {skipped_count}")
            
            # Add to collection in optimized batches
            batch_size = min(config.indexing.batch_size, 100)  # Cap at 100 for stability
            indexed_count = 0
            batch_errors = 0
            
            for i in range(0, len(documents), batch_size):
                try:
                    batch_docs = documents[i:i + batch_size]
                    batch_metadata = metadatas[i:i + batch_size]
                    batch_ids = ids[i:i + batch_size]
                    
                    # Add batch to collection
                    collection.add(
                        documents=batch_docs,
                        metadatas=batch_metadata,
                        ids=batch_ids
                    )
                    
                    indexed_count += len(batch_docs)
                    logger.info(f"Indexed batch {i//batch_size + 1}: {indexed_count}/{len(documents)} elements")
                    
                    # Small delay between batches to prevent overwhelming the system
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error indexing batch {i//batch_size + 1}: {e}")
                    batch_errors += 1
                    # Continue with next batch rather than failing completely
                    continue
            
            # Update last index time
            self._last_index_time = datetime.now()
            
            elapsed_time = time.time() - start_time
            
            result = {
                "success": True,
                "indexed_count": indexed_count,
                "total_elements": len(elements),
                "processed_elements": processed_count,
                "skipped_count": skipped_count,
                "batch_errors": batch_errors,
                "indexed_at": self._last_index_time.isoformat(),
                "elapsed_seconds": round(elapsed_time, 2)
            }
            
            if batch_errors > 0:
                result["warning"] = f"{batch_errors} batches failed during indexing"
            
            logger.info(f"Indexing completed in {elapsed_time:.2f}s: {indexed_count} elements indexed")
            return result
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            error_msg = f"Failed to index AF elements: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": str(e),
                "indexed_count": 0,
                "elapsed_seconds": round(elapsed_time, 2)
            }
    
    async def search_af_elements(self, query: str, n_results: int = 10, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Search AF elements using vector similarity with improved error handling"""
        try:
            collection = await self.get_collection()
            
            # Build where clause for filtering
            where_clause = {"element_type": "af_element"}
            if filters:
                # Handle different filter types properly
                for key, value in filters.items():
                    if isinstance(value, (str, int, float, bool)):
                        where_clause[key] = value
                    elif isinstance(value, list):
                        # For list filters, we might need to use $in operator
                        # This depends on ChromaDB version and capabilities
                        where_clause[key] = {"$in": value}
            
            # Perform vector search with error handling
            try:
                results = collection.query(
                    query_texts=[query],
                    n_results=min(n_results, 100),  # Cap results for performance
                    where=where_clause,
                    include=["metadatas", "documents", "distances"]
                )
            except Exception as e:
                logger.warning(f"Vector search failed, falling back to metadata search: {e}")
                # Fallback to metadata-only search
                results = collection.get(
                    where=where_clause,
                    limit=min(n_results, 100),
                    include=["metadatas", "documents"]
                )
                # Add dummy distances for compatibility
                if results["ids"]:
                    results["distances"] = [[0.5] * len(results["ids"])]
                else:
                    results["distances"] = [[]]
            
            # Format results with enhanced information
            formatted_results = []
            if results["ids"] and results["ids"][0]:
                for i, element_id in enumerate(results["ids"][0]):
                    metadata = results["metadatas"][0][i]
                    
                    result = {
                        "id": element_id,
                        "webid": metadata.get("webid", ""),
                        "name": metadata.get("name", ""),
                        "path": metadata.get("path", ""),
                        "template_name": metadata.get("template_name", ""),
                        "template_category": metadata.get("template_category", ""),
                        "has_children": metadata.get("has_children", False),
                        "business_hierarchy": metadata.get("business_hierarchy", ""),
                        "business_path_level": metadata.get("business_path_level", 0),
                        "similarity_score": 1 - results["distances"][0][i] if results["distances"][0] else 0.5,
                        "document_text": results["documents"][0][i] if results["documents"] else ""
                    }
                    formatted_results.append(result)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Failed to search AF elements: {str(e)}")
            return []
    
    async def get_elements_by_template(self, template_name: str, n_results: int = 50) -> List[Dict[str, Any]]:
        """Get elements by template name with enhanced filtering"""
        try:
            collection = await self.get_collection()
            
            # Use get method for exact template matching
            try:
                results = collection.get(
                    where={"template_name": template_name},
                    limit=min(n_results, 200),  # Reasonable limit
                    include=["metadatas", "documents"]
                )
            except Exception as e:
                logger.warning(f"Template search failed, trying case-insensitive: {e}")
                # Try with vector search as fallback
                return await self.search_af_elements(f"template {template_name}", n_results)
            
            formatted_results = []
            if results["ids"]:
                for i, element_id in enumerate(results["ids"]):
                    metadata = results["metadatas"][i]
                    
                    result = {
                        "id": element_id,
                        "webid": metadata.get("webid", ""),
                        "name": metadata.get("name", ""),
                        "path": metadata.get("path", ""),
                        "template_name": metadata.get("template_name", ""),
                        "template_category": metadata.get("template_category", ""),
                        "has_children": metadata.get("has_children", False),
                        "business_hierarchy": metadata.get("business_hierarchy", ""),
                        "document_text": results["documents"][i] if results["documents"] else ""
                    }
                    formatted_results.append(result)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Failed to get elements by template: {str(e)}")
            return []
    
    async def get_elements_by_path_pattern(self, path_pattern: str, n_results: int = 50) -> List[Dict[str, Any]]:
        """Get elements by path pattern with improved matching"""
        try:
            # Use vector search with path-focused query
            query = f"path location {path_pattern}"
            results = await self.search_af_elements(query, n_results * 2)  # Get more to filter
            
            # Filter by path in post-processing for better accuracy
            filtered_results = []
            pattern_lower = path_pattern.lower()
            
            for r in results:
                path_lower = r.get("path", "").lower()
                hierarchy_lower = r.get("business_hierarchy", "").lower()
                
                if (pattern_lower in path_lower or 
                    pattern_lower in hierarchy_lower or
                    any(pattern_lower in part.lower() for part in path_lower.split('\\') if part)):
                    filtered_results.append(r)
                    
                if len(filtered_results) >= n_results:
                    break
            
            return filtered_results
            
        except Exception as e:
            logger.error(f"Failed to get elements by path pattern: {str(e)}")
            return []
    
    async def get_elements_by_hierarchy_level(self, level: str, value: str, n_results: int = 50) -> List[Dict[str, Any]]:
        """Get elements by specific hierarchy level (area, unit, equipment, etc.)"""
        try:
            collection = await self.get_collection()
            
            # Map level names to metadata keys
            level_key_map = {
                "area": "hierarchy_area",
                "unit": "hierarchy_unit", 
                "equipment": "hierarchy_equipment",
                "component": "hierarchy_component",
                "item": "hierarchy_item"
            }
            
            level_key = level_key_map.get(level.lower(), f"hierarchy_{level.lower()}")
            
            results = collection.get(
                where={level_key: value},
                limit=min(n_results, 200),
                include=["metadatas", "documents"]
            )
            
            formatted_results = []
            if results["ids"]:
                for i, element_id in enumerate(results["ids"]):
                    metadata = results["metadatas"][i]
                    
                    result = {
                        "id": element_id,
                        "webid": metadata.get("webid", ""),
                        "name": metadata.get("name", ""),
                        "path": metadata.get("path", ""),
                        "template_name": metadata.get("template_name", ""),
                        "has_children": metadata.get("has_children", False),
                        "business_hierarchy": metadata.get("business_hierarchy", ""),
                        "hierarchy_level": level,
                        "hierarchy_value": value,
                        "document_text": results["documents"][i] if results["documents"] else ""
                    }
                    formatted_results.append(result)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Failed to get elements by hierarchy level: {str(e)}")
            return []
    
    async def clear_collection(self) -> bool:
        """Clear all elements from the collection with proper error handling"""
        try:
            lock = await self._get_lock()
            async with lock:
                client = self.get_client()
                
                # Delete the collection
                client.delete_collection(config.chroma.collection_name)
                self._collection = None
                self._last_index_time = None
                
                logger.info(f"Cleared collection: {config.chroma.collection_name}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to clear collection: {str(e)}")
            return False
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics with comprehensive information"""
        try:
            collection = await self.get_collection()
            count = collection.count()
            
            # Try to get some sample metadata for stats
            sample_data = None
            try:
                sample = collection.get(limit=1, include=["metadatas"])
                if sample["ids"]:
                    sample_data = sample["metadatas"][0]
            except Exception:
                pass
            
            stats = {
                "total_elements": count,
                "collection_name": config.chroma.collection_name,
                "last_indexed": self._last_index_time.isoformat() if self._last_index_time else None,
                "client_type": config.chroma.client_type,
                "client_initialized": self._client_initialized,
                "indexing_enabled": config.indexing.enabled
            }
            
            if sample_data:
                stats["sample_metadata_keys"] = list(sample_data.keys())
                
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {str(e)}")
            return {
                "error": str(e),
                "client_initialized": self._client_initialized,
                "indexing_enabled": config.indexing.enabled
            }
    
    def should_refresh_index(self) -> bool:
        """Check if index should be refreshed with improved logic"""
        if not config.indexing.enabled:
            logger.debug("Indexing is disabled")
            return False
        
        if not self._last_index_time:
            logger.debug("No previous index time, refresh needed")
            return True
        
        refresh_threshold = datetime.now() - timedelta(hours=config.indexing.refresh_interval_hours)
        should_refresh = self._last_index_time < refresh_threshold
        
        if should_refresh:
            logger.debug(f"Index is older than {config.indexing.refresh_interval_hours} hours, refresh needed")
        else:
            hours_since_index = (datetime.now() - self._last_index_time).total_seconds() / 3600
            logger.debug(f"Index is {hours_since_index:.1f} hours old, no refresh needed")
            
        return should_refresh
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on vector database"""
        try:
            # Test basic connectivity
            collection = await self.get_collection()
            count = collection.count()
            
            # Test search functionality
            test_query_start = time.time()
            test_results = await self.search_af_elements("test", 1)
            search_time = (time.time() - test_query_start) * 1000
            
            return {
                "status": "healthy",
                "total_elements": count,
                "search_test_time_ms": round(search_time, 2),
                "last_indexed": self._last_index_time.isoformat() if self._last_index_time else None,
                "client_type": config.chroma.client_type
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "client_type": config.chroma.client_type
            }

# Global vector database manager instance
vector_db = VectorDBManager()
