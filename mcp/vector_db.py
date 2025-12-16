"""
Production-Ready Vector Database Manager for AVEVA PI AF Elements

Key Features:
- Indexes AF Elements WITH their attributes in a single document
- Semantic search across element names, paths, templates, AND attributes
- Metadata flags for quick filtering (has_healthscore, has_temperature, etc.)
- Intelligent keyword extraction from attribute names
- Efficient batch processing with progress tracking
- Comprehensive error handling and logging

Author: Data Center Reliability Team
Version: 2.0 - Integrated Attribute Indexing
"""

import chromadb
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import json
import time
from config import config, AF_TEMPLATE_CATEGORIES

logger = logging.getLogger(__name__)


class VectorDBManager:
    """Manages ChromaDB integration for AF elements and attributes indexing with semantic search"""
    
    def __init__(self):
        self._client = None
        self._collection = None
        self._last_index_time = None
        self._initialization_lock = None
        self._client_initialized = False
        
    async def _get_lock(self):
        """Get or create async lock for current event loop"""
        if self._initialization_lock is None:
            try:
                asyncio.get_running_loop()
                self._initialization_lock = asyncio.Lock()
            except RuntimeError:
                pass
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
                logger.info(f"✅ ChromaDB client initialized: {config.chroma.client_type}")
                
            except Exception as e:
                logger.error(f"❌ Failed to initialize ChromaDB client: {e}")
                raise
        
        return self._client
    
    async def get_collection(self):
        """Get or create collection for AF elements with async protection"""
        if self._collection is None:
            lock = await self._get_lock()
            if lock:
                async with lock:
                    if self._collection is None:  # Double-check pattern
                        await self._create_collection()
            else:
                # Fallback for non-async contexts
                await self._create_collection()
        
        return self._collection
    
    async def _create_collection(self):
        """Internal method to create or get collection"""
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
                    metadata={
                        "description": "AF Elements with integrated attributes for semantic search",
                        "version": "2.0",
                        "created_at": datetime.now().isoformat()
                    }
                )
                logger.info(f"Created new collection: {config.chroma.collection_name}")
                
        except Exception as e:
            logger.error(f"Failed to get/create collection: {e}")
            raise
    
    def prepare_element_for_indexing(
        self, 
        element: Dict[str, Any], 
        attributes: List[Dict[str, Any]] = None
    ) -> Tuple[str, str, Dict[str, Any]]:
        """
        Prepare an AF element AND its attributes for vector indexing
        
        This is the core indexing method that creates searchable documents
        including both element and attribute information.
        
        Args:
            element: AF Element data from PI Web API
            attributes: Optional list of element's attributes
            
        Returns:
            Tuple of (document_text, element_id, metadata)
        """
        doc_parts = []
        
        # ============================================================
        # ELEMENT INFORMATION
        # ============================================================
        name = element.get('Name', '')
        description = element.get('Description', '')
        
        doc_parts.append(f"Element Name: {name}")
        
        if description and description.strip():
            doc_parts.append(f"Description: {description}")
        
        # Path information - enhanced processing for better search
        path = element.get('Path', '')
        if path:
            path_parts = [p.strip() for p in path.split('\\') if p.strip()]
            doc_parts.append(f"Full Path: {path}")
            
            # Skip server and database parts, keep business-relevant hierarchy
            if len(path_parts) > 2:
                business_path_parts = path_parts[2:]
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
        
        # Element type information
        if element.get('HasChildren', False):
            doc_parts.append("Element Type: Container")
            doc_parts.append("Has Sub-elements: Yes")
        else:
            doc_parts.append("Element Type: Leaf Node")
            doc_parts.append("Has Sub-elements: No")
        
        # ============================================================
        # ATTRIBUTE INFORMATION (INTEGRATED)
        # ============================================================
        attribute_names = []
        attribute_keywords = []
        attribute_units = []
        
        if attributes and len(attributes) > 0:
            doc_parts.append(f"\n=== Available Measurements and Data Points ({len(attributes)} attributes) ===")
            
            for attr in attributes:
                attr_name = attr.get('Name', '')
                attr_type = attr.get('Type', '')
                units = attr.get('DefaultUnitsNameAbbreviation', '')
                data_ref = attr.get('DataReferencePlugIn', '')
                description = attr.get('Description', '') 
                
                # Build attribute description for document
                attr_line = f"Attribute: {attr_name}"
                if description:  # ← ADD THIS
                    attr_line += f" - {description}"
                if units:
                    attr_line += f" (Units: {units})"
                    attribute_units.append(units)
                    
                if attr_type:
                    attr_line += f" [Type: {attr_type}]"
                
                doc_parts.append(attr_line)
                attribute_names.append(attr_name)
                
                # Extract engineering keywords from attribute name
                keywords = self._extract_attribute_keywords(attr_name)
                attribute_keywords.extend(keywords)
            
            # Add consolidated keywords section for better semantic search
            if attribute_keywords:
                unique_keywords = list(set(attribute_keywords))
                doc_parts.append(f"\nMeasurement Types Available: {', '.join(unique_keywords)}")
                
            # Add units summary
            if attribute_units:
                unique_units = list(set(attribute_units))
                doc_parts.append(f"Units of Measurement: {', '.join(unique_units)}")
        
        # Join all parts with proper spacing
        document_text = "\n".join(doc_parts)
        
        # ============================================================
        # METADATA - Enhanced with Attribute Flags
        # ============================================================
        metadata = {
            # Element core metadata
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
        
        # Enhanced path level information
        if path:
            path_parts = [p.strip() for p in path.split('\\') if p.strip()]
            total_path_level = len(path_parts)
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
                
                # Store parent information for traversal
                if len(business_components) >= 1:
                    metadata["parent_area"] = business_components[0]
                if len(business_components) >= 2:
                    metadata["equipment_unit"] = business_components[1]
                if len(business_components) >= 3:
                    metadata["equipment_name"] = business_components[2]
        
        # ============================================================
        # ATTRIBUTE METADATA FLAGS - NEW!
        # ============================================================
        if attributes:
            metadata["attribute_count"] = len(attributes)
            
            # Store attribute names (limited to avoid size issues)
            metadata["attribute_names"] = json.dumps([a.get('Name', '') for a in attributes[:30]])
            
            # Boolean flags for common measurement types - enables quick filtering
            attr_names_lower = [a.get('Name', '').lower() for a in attributes]
            
            metadata["has_healthscore"] = any('health' in name for name in attr_names_lower)
            metadata["has_temperature"] = any('temp' in name for name in attr_names_lower)
            metadata["has_pressure"] = any('pres' in name for name in attr_names_lower)
            metadata["has_vibration"] = any('vibr' in name for name in attr_names_lower)
            metadata["has_current"] = any('curr' in name or 'amp' in name for name in attr_names_lower)
            metadata["has_voltage"] = any('volt' in name for name in attr_names_lower)
            metadata["has_power"] = any('pow' in name or 'watt' in name for name in attr_names_lower)
            metadata["has_flow"] = any('flow' in name for name in attr_names_lower)
            metadata["has_humidity"] = any('humid' in name for name in attr_names_lower)
            metadata["has_status"] = any('status' in name or 'state' in name for name in attr_names_lower)
            metadata["has_alarm"] = any('alarm' in name or 'alert' in name for name in attr_names_lower)
            
            # Store measurement types as JSON array
            if attribute_keywords:
                unique_keywords = list(set(attribute_keywords))
                metadata["measurement_types"] = json.dumps(unique_keywords[:15])  # Limit to 15
            
            # Store units if available
            if attribute_units:
                unique_units = list(set(attribute_units))
                metadata["units"] = json.dumps(unique_units[:10])
        else:
            metadata["attribute_count"] = 0
            metadata["has_healthscore"] = False
            metadata["has_temperature"] = False
        
        # Add searchable keywords
        keywords = []
        if name:
            keywords.append(name.lower())
        if template_name:
            keywords.append(template_name.lower())
        if description:
            # Extract meaningful words from description
            desc_words = [w.strip().lower() for w in description.split() if len(w.strip()) > 2]
            keywords.extend(desc_words[:5])
        
        # Add attribute keywords
        if attribute_keywords:
            keywords.extend(attribute_keywords[:10])
        
        metadata["keywords"] = " ".join(keywords)
        
        # Create unique ID with better collision avoidance
        element_id = f"af_element_{element.get('WebId', element.get('Id', str(hash(path))))}"
        
        return document_text, element_id, metadata
    
    def _extract_attribute_keywords(self, attr_name: str) -> List[str]:
        """
        Extract engineering keywords from attribute names
        
        This helps with semantic search by identifying measurement types
        even when users don't use exact attribute names.
        
        Args:
            attr_name: Attribute name from PI AF
            
        Returns:
            List of engineering keywords
        """
        keywords = []
        attr_lower = attr_name.lower()
        
        # Comprehensive measurement type mapping
        measurement_map = {
            # Temperature
            'temp': 'temperature',
            'degc': 'temperature',
            'degf': 'temperature',
            
            # Pressure
            'pres': 'pressure',
            'press': 'pressure',
            'psi': 'pressure',
            'bar': 'pressure',
            'pa': 'pressure',
            
            # Flow
            'flow': 'flow_rate',
            'gpm': 'flow_rate',
            'lpm': 'flow_rate',
            'm3/h': 'flow_rate',
            
            # Electrical
            'volt': 'voltage',
            'curr': 'current',
            'amp': 'current',
            'pow': 'power',
            'watt': 'power',
            'kw': 'power',
            'mw': 'power',
            'freq': 'frequency',
            'hz': 'frequency',
            'pf': 'power_factor',
            
            # Mechanical
            'vibr': 'vibration',
            'accel': 'acceleration',
            'speed': 'speed',
            'rpm': 'speed',
            'torque': 'torque',
            
            # Environmental
            'humid': 'humidity',
            'rh': 'humidity',
            
            # Levels
            'level': 'level',
            'height': 'level',
            'dc': 'health_score',      # Data Center score
            'eyd': 'health_score',     # End Year Degradation
            'myd': 'health_score',     # Mid Year Degradation  
            'net': 'health_score',
            # Health and Status
            'health': 'health_score',
            'condition': 'health_score',
            'status': 'status',
            'state': 'status',
            'alarm': 'alarm',
            'alert': 'alarm',
            'warning': 'alarm',
            'fault': 'fault',
            'error': 'error',
            
            # Control
            'setpoint': 'setpoint',
            'sp': 'setpoint',
            'pv': 'process_value',
            'mv': 'manipulated_variable',
            'output': 'control_output',
            
            # Performance
            'efficiency': 'efficiency',
            'eff': 'efficiency',
            'utilization': 'utilization',
            'load': 'load',
            'capacity': 'capacity',
            
            # Quality
            'quality': 'data_quality',
            'reliability': 'reliability'
        }
        
        # Check for matches
        for key, value in measurement_map.items():
            if key in attr_lower:
                keywords.append(value)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for k in keywords:
            if k not in seen:
                seen.add(k)
                unique_keywords.append(k)
        
        return unique_keywords
    
    async def index_af_elements(self, elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Index AF elements WITH their attributes in ChromaDB
        
        This is the main indexing method that:
        1. Fetches attributes for each element from PI Web API
        2. Creates searchable documents with element + attribute info
        3. Indexes in batches for performance
        
        Args:
            elements: List of AF element dictionaries from PI Web API
            
        Returns:
            Indexing result with statistics
        """
        start_time = time.time()
        
        try:
            collection = await self.get_collection()
            
            if not elements:
                logger.warning("No elements provided for indexing")
                return {"success": False, "error": "No elements provided", "indexed_count": 0}
            
            logger.info(f"🔄 Starting indexing of {len(elements)} AF elements WITH attributes")
            
            # Clear existing elements to avoid duplicates
            try:
                collection.delete(where={"element_type": "af_element"})
                logger.info("🗑️  Cleared existing AF elements from collection")
            except Exception as e:
                logger.warning(f"Could not clear existing elements: {e}")
            
            # Import PI client for fetching attributes
            # Note: Import here to avoid circular dependency
            try:
                from pi_mcp_server import get_pi_client
                client = get_pi_client()
            except ImportError:
                logger.error("Cannot import get_pi_client - indexing without attributes")
                client = None
            
            documents = []
            metadatas = []
            ids = []
            
            processed_count = 0
            skipped_count = 0
            attributes_fetched = 0
            
            for i, element in enumerate(elements):
                try:
                    # Skip elements with missing required fields
                    if not element.get('Name') or not element.get('Path'):
                        skipped_count += 1
                        continue
                    
                    # Fetch attributes for this element
                    element_web_id = element.get('WebId')
                    attributes = []
                    
                    if element_web_id and client:
                        try:
                            # Get attributes for this element
                            attrs_response = await client.get(
                                f"/elements/{element_web_id}/attributes",
                                params={
                                    "maxCount": 100,  # Get up to 100 attributes
                                    "selectedFields": "Items.Name;Items.WebId;Items.Type;Items.Description;Items.DefaultUnitsNameAbbreviation;Items.DataReferencePlugIn"
                                }
                            )
                            attributes = attrs_response.get("Items", [])
                            attributes_fetched += len(attributes)
                            
                        except Exception as e:
                            logger.debug(f"Could not fetch attributes for {element.get('Name')}: {e}")
                            # Continue without attributes - element will still be indexed
                    
                    # Prepare element WITH attributes for indexing
                    doc_text, element_id, metadata = self.prepare_element_for_indexing(element, attributes)
                    
                    documents.append(doc_text)
                    metadatas.append(metadata)
                    ids.append(element_id)
                    processed_count += 1
                    
                    # Progress logging every 25 elements
                    if (i + 1) % 25 == 0:
                        logger.info(f"📊 Prepared {i + 1}/{len(elements)} elements (avg {attributes_fetched//(i+1)} attrs/element)")
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
            
            logger.info(f"✅ Prepared {processed_count} elements, {attributes_fetched} attributes, skipped {skipped_count}")
            
            # Add to collection in optimized batches
            batch_size = min(config.indexing.batch_size, 50)
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
                    logger.info(f"💾 Indexed batch {i//batch_size + 1}: {indexed_count}/{len(documents)} elements")
                    
                    # Small delay between batches
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error indexing batch {i//batch_size + 1}: {e}")
                    batch_errors += 1
                    continue
            
            # Update last index time
            self._last_index_time = datetime.now()
            
            elapsed_time = time.time() - start_time
            
            result = {
                "success": True,
                "indexed_count": indexed_count,
                "total_elements": len(elements),
                "processed_elements": processed_count,
                "attributes_fetched": attributes_fetched,
                "skipped_count": skipped_count,
                "batch_errors": batch_errors,
                "indexed_at": self._last_index_time.isoformat(),
                "elapsed_seconds": round(elapsed_time, 2),
                "avg_attributes_per_element": round(attributes_fetched / processed_count, 1) if processed_count > 0 else 0
            }
            
            if batch_errors > 0:
                result["warning"] = f"{batch_errors} batches failed during indexing"
            
            logger.info(f"🎉 Indexing completed in {elapsed_time:.2f}s: {indexed_count} elements with {attributes_fetched} attributes")
            return result
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            error_msg = f"Failed to index AF elements: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": str(e),
                "indexed_count": 0,
                "elapsed_seconds": round(elapsed_time, 2)
            }
    
    async def search_af_elements(
        self, 
        query: str, 
        n_results: int = 10, 
        filters: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Search AF elements using vector similarity with improved error handling
        
        This searches across element names, paths, templates, AND attributes.
        
        Args:
            query: Natural language search query
            n_results: Maximum number of results
            filters: Optional metadata filters (e.g., {"template_name": "BuswayJoint"})
            
        Returns:
            List of matching elements with metadata and similarity scores
        """
        try:
            collection = await self.get_collection()
            
            # Build where clause for filtering
            where_clause = {"element_type": "af_element"}
            if filters:
                for key, value in filters.items():
                    if isinstance(value, (str, int, float, bool)):
                        where_clause[key] = value
                    elif isinstance(value, list):
                        where_clause[key] = {"$in": value}
            
            # Perform vector search
            try:
                results = collection.query(
                    query_texts=[query],
                    n_results=min(n_results, 100),
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
                        
                        # Attribute information
                        "attribute_count": metadata.get("attribute_count", 0),
                        "has_healthscore": metadata.get("has_healthscore", False),
                        "has_temperature": metadata.get("has_temperature", False),
                        "has_vibration": metadata.get("has_vibration", False),
                        "measurement_types": json.loads(metadata.get("measurement_types", "[]")),
                        
                        # Document preview for debugging
                        "document_preview": results["documents"][0][i][:200] + "..." if results["documents"] else ""
                    }
                    formatted_results.append(result)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Failed to search AF elements: {str(e)}")
            return []
    
    async def get_elements_by_template(self, template_name: str, n_results: int = 50) -> List[Dict[str, Any]]:
        """Get elements by exact template name match"""
        try:
            collection = await self.get_collection()
            
            results = collection.get(
                where={"template_name": template_name},
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
                        "template_category": metadata.get("template_category", ""),
                        "has_children": metadata.get("has_children", False),
                        "business_hierarchy": metadata.get("business_hierarchy", ""),
                        "attribute_count": metadata.get("attribute_count", 0),
                        "has_healthscore": metadata.get("has_healthscore", False)
                    }
                    formatted_results.append(result)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Failed to get elements by template: {str(e)}")
            return []
    
    async def get_elements_by_hierarchy_level(
        self, 
        level: str, 
        value: str, 
        n_results: int = 50
    ) -> List[Dict[str, Any]]:
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
                        "attribute_count": metadata.get("attribute_count", 0)
                    }
                    formatted_results.append(result)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Failed to get elements by hierarchy level: {str(e)}")
            return []
    
    async def clear_collection(self) -> bool:
        """Clear all elements from the collection"""
        try:
            lock = await self._get_lock()
            if lock:
                async with lock:
                    client = self.get_client()
                    client.delete_collection(config.chroma.collection_name)
                    self._collection = None
                    self._last_index_time = None
                    logger.info(f"🗑️  Cleared collection: {config.chroma.collection_name}")
                    return True
            else:
                # Non-async fallback
                client = self.get_client()
                client.delete_collection(config.chroma.collection_name)
                self._collection = None
                self._last_index_time = None
                return True
                
        except Exception as e:
            logger.error(f"Failed to clear collection: {str(e)}")
            return False
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get comprehensive collection statistics"""
        try:
            collection = await self.get_collection()
            count = collection.count()
            
            # Get sample for statistics
            sample_data = None
            try:
                sample = collection.get(limit=1, include=["metadatas"])
                if sample["ids"]:
                    sample_data = sample["metadatas"][0]
            except Exception:
                pass
            
            # Get counts by measurement type flags
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
            
            # Try to get measurement type statistics
            try:
                health_count = collection.count(where={"has_healthscore": True})
                temp_count = collection.count(where={"has_temperature": True})
                vibration_count = collection.count(where={"has_vibration": True})
                
                stats["elements_with_healthscore"] = health_count
                stats["elements_with_temperature"] = temp_count
                stats["elements_with_vibration"] = vibration_count
            except Exception:
                pass
                
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {str(e)}")
            return {
                "error": str(e),
                "client_initialized": self._client_initialized,
                "indexing_enabled": config.indexing.enabled
            }
    
    def should_refresh_index(self) -> bool:
        """Check if index should be refreshed"""
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
                "client_type": config.chroma.client_type,
                "collection_name": config.chroma.collection_name
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "client_type": config.chroma.client_type
            }


# Global vector database manager instance
vector_db = VectorDBManager()
