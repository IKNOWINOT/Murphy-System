"""
Artifact Manager
Handles CRUD operations, versioning, and storage for artifacts
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from artifact_generation_system import Artifact, ArtifactType, ArtifactStatus

class ArtifactManager:
    """Manages artifact lifecycle and storage"""
    
    def __init__(self, storage_path: str = "/workspace/artifacts"):
        self.storage_path = storage_path
        self.artifacts: Dict[str, Artifact] = {}
        self.version_history: Dict[str, List[Dict]] = {}
        
        # Create storage directory if it doesn't exist
        os.makedirs(storage_path, exist_ok=True)
        
    def add_artifact(self, artifact: Artifact) -> str:
        """Add a new artifact to the manager"""
        self.artifacts[artifact.id] = artifact
        
        # Initialize version history
        if artifact.id not in self.version_history:
            self.version_history[artifact.id] = []
            
        # Add initial version
        self.version_history[artifact.id].append({
            'version': artifact.version,
            'created_at': artifact.created_at,
            'quality_score': artifact.quality_score,
            'status': artifact.status.value,
            'metadata': artifact.metadata.copy()
        })
        
        # Save artifact content to file
        if artifact.content:
            self._save_to_file(artifact)
            
        return artifact.id
        
    def get_artifact(self, artifact_id: str) -> Optional[Artifact]:
        """Get artifact by ID"""
        return self.artifacts.get(artifact_id)
        
    def list_artifacts(self, artifact_type: Optional[str] = None, 
                      status: Optional[str] = None) -> List[Dict]:
        """List all artifacts with optional filtering"""
        results = []
        
        for artifact in self.artifacts.values():
            # Apply filters
            if artifact_type and artifact.type.value != artifact_type:
                continue
            if status and artifact.status.value != status:
                continue
                
            results.append(artifact.to_dict())
            
        # Sort by created_at descending
        results.sort(key=lambda x: x['created_at'], reverse=True)
        return results
        
    def update_artifact(self, artifact_id: str, updates: Dict) -> Optional[Artifact]:
        """Update an existing artifact"""
        artifact = self.artifacts.get(artifact_id)
        if not artifact:
            return None
            
        # Update allowed fields
        if 'name' in updates:
            artifact.name = updates['name']
        if 'content' in updates:
            artifact.content = updates['content']
            self._save_to_file(artifact)
        if 'metadata' in updates:
            artifact.metadata.update(updates['metadata'])
        if 'status' in updates:
            try:
                artifact.status = ArtifactStatus(updates['status'])
            except ValueError:
                pass
                
        artifact.updated_at = datetime.now().isoformat()
        
        return artifact
        
    def delete_artifact(self, artifact_id: str) -> bool:
        """Delete an artifact"""
        artifact = self.artifacts.get(artifact_id)
        if not artifact:
            return False
            
        # Delete file if it exists
        if artifact.file_path and os.path.exists(artifact.file_path):
            try:
                os.remove(artifact.file_path)
            except:
                pass
                
        # Remove from memory
        del self.artifacts[artifact_id]
        if artifact_id in self.version_history:
            del self.version_history[artifact_id]
            
        return True
        
    def create_version(self, artifact_id: str, content: str, 
                      metadata: Optional[Dict] = None) -> Optional[Artifact]:
        """Create a new version of an artifact"""
        artifact = self.artifacts.get(artifact_id)
        if not artifact:
            return None
            
        # Increment version
        artifact.version += 1
        artifact.content = content
        artifact.updated_at = datetime.now().isoformat()
        
        if metadata:
            artifact.metadata.update(metadata)
            
        # Save to version history
        self.version_history[artifact_id].append({
            'version': artifact.version,
            'created_at': artifact.updated_at,
            'quality_score': artifact.quality_score,
            'status': artifact.status.value,
            'metadata': artifact.metadata.copy()
        })
        
        # Save new version to file
        self._save_to_file(artifact)
        
        return artifact
        
    def get_version_history(self, artifact_id: str) -> List[Dict]:
        """Get version history for an artifact"""
        return self.version_history.get(artifact_id, [])
        
    def rollback_version(self, artifact_id: str, version: int) -> Optional[Artifact]:
        """Rollback artifact to a specific version"""
        artifact = self.artifacts.get(artifact_id)
        if not artifact:
            return None
            
        history = self.version_history.get(artifact_id, [])
        target_version = None
        
        for v in history:
            if v['version'] == version:
                target_version = v
                break
                
        if not target_version:
            return None
            
        # Restore metadata from target version
        artifact.metadata = target_version['metadata'].copy()
        artifact.quality_score = target_version['quality_score']
        artifact.status = ArtifactStatus(target_version['status'])
        artifact.updated_at = datetime.now().isoformat()
        
        return artifact
        
    def convert_format(self, artifact_id: str, target_format: str) -> Optional[Artifact]:
        """Convert artifact to a different format"""
        artifact = self.artifacts.get(artifact_id)
        if not artifact:
            return None
            
        # Create a new artifact with converted format
        from artifact_generation_system import Artifact as NewArtifact
        
        converted = NewArtifact(
            ArtifactType(target_format),
            f"{artifact.name}_converted",
            artifact.source_doc_id
        )
        
        # Copy content and metadata
        converted.content = artifact.content
        converted.metadata = artifact.metadata.copy()
        converted.metadata['converted_from'] = artifact.type.value
        converted.metadata['original_id'] = artifact.id
        converted.quality_score = artifact.quality_score * 0.9  # Slight quality reduction
        converted.status = ArtifactStatus.COMPLETE
        converted.format = target_format
        
        # Add to manager
        self.add_artifact(converted)
        
        return converted
        
    def search_artifacts(self, query: str) -> List[Dict]:
        """Search artifacts by name or content"""
        results = []
        query_lower = query.lower()
        
        for artifact in self.artifacts.values():
            # Search in name
            if query_lower in artifact.name.lower():
                results.append(artifact.to_dict())
                continue
                
            # Search in content
            if artifact.content and query_lower in artifact.content.lower():
                results.append(artifact.to_dict())
                continue
                
            # Search in metadata
            metadata_str = json.dumps(artifact.metadata).lower()
            if query_lower in metadata_str:
                results.append(artifact.to_dict())
                
        return results
        
    def get_statistics(self) -> Dict:
        """Get artifact statistics"""
        stats = {
            'total_artifacts': len(self.artifacts),
            'by_type': {},
            'by_status': {},
            'total_size': 0,
            'average_quality': 0.0
        }
        
        quality_sum = 0.0
        
        for artifact in self.artifacts.values():
            # Count by type
            type_key = artifact.type.value
            stats['by_type'][type_key] = stats['by_type'].get(type_key, 0) + 1
            
            # Count by status
            status_key = artifact.status.value
            stats['by_status'][status_key] = stats['by_status'].get(status_key, 0) + 1
            
            # Sum file sizes
            stats['total_size'] += artifact.file_size
            
            # Sum quality scores
            quality_sum += artifact.quality_score
            
        # Calculate average quality
        if len(self.artifacts) > 0:
            stats['average_quality'] = quality_sum / len(self.artifacts)
            
        return stats
        
    def _save_to_file(self, artifact: Artifact) -> bool:
        """Save artifact content to file"""
        if not artifact.content or not artifact.file_path:
            return False
            
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(artifact.file_path), exist_ok=True)
            
            # Write content to file
            with open(artifact.file_path, 'w', encoding='utf-8') as f:
                f.write(artifact.content)
                
            # Update file size
            artifact.file_size = os.path.getsize(artifact.file_path)
            
            return True
        except Exception as e:
            print(f"Error saving artifact to file: {e}")
            return False
            
    def _load_from_file(self, artifact: Artifact) -> bool:
        """Load artifact content from file"""
        if not artifact.file_path or not os.path.exists(artifact.file_path):
            return False
            
        try:
            with open(artifact.file_path, 'r', encoding='utf-8') as f:
                artifact.content = f.read()
            return True
        except Exception as e:
            print(f"Error loading artifact from file: {e}")
            return False
            
    def export_artifact(self, artifact_id: str, export_path: str) -> bool:
        """Export artifact to a specific path"""
        artifact = self.artifacts.get(artifact_id)
        if not artifact or not artifact.content:
            return False
            
        try:
            # Ensure export directory exists
            os.makedirs(os.path.dirname(export_path), exist_ok=True)
            
            # Write to export path
            with open(export_path, 'w', encoding='utf-8') as f:
                f.write(artifact.content)
                
            return True
        except Exception as e:
            print(f"Error exporting artifact: {e}")
            return False
            
    def import_artifact(self, file_path: str, artifact_type: str, 
                       name: str, source_doc_id: str) -> Optional[Artifact]:
        """Import an artifact from a file"""
        if not os.path.exists(file_path):
            return None
            
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Create new artifact
            from artifact_generation_system import Artifact as NewArtifact
            
            artifact = NewArtifact(
                ArtifactType(artifact_type),
                name,
                source_doc_id
            )
            
            artifact.content = content
            artifact.status = ArtifactStatus.COMPLETE
            artifact.file_size = len(content.encode('utf-8'))
            artifact.metadata['imported_from'] = file_path
            artifact.quality_score = 0.8  # Default quality for imported artifacts
            
            # Add to manager
            self.add_artifact(artifact)
            
            return artifact
            
        except Exception as e:
            print(f"Error importing artifact: {e}")
            return None
            
    def cleanup_old_versions(self, artifact_id: str, keep_versions: int = 5) -> int:
        """Clean up old versions, keeping only the most recent N versions"""
        history = self.version_history.get(artifact_id, [])
        
        if len(history) <= keep_versions:
            return 0
            
        # Sort by version descending
        history.sort(key=lambda x: x['version'], reverse=True)
        
        # Keep only the most recent versions
        self.version_history[artifact_id] = history[:keep_versions]
        
        # Return number of versions removed
        return len(history) - keep_versions
        
    def get_artifacts_by_source(self, source_doc_id: str) -> List[Dict]:
        """Get all artifacts generated from a specific source document"""
        results = []
        
        for artifact in self.artifacts.values():
            if artifact.source_doc_id == source_doc_id:
                results.append(artifact.to_dict())
                
        return results
        
    def validate_all_artifacts(self) -> Dict:
        """Validate all artifacts and return results"""
        results = {
            'total': len(self.artifacts),
            'valid': 0,
            'invalid': 0,
            'issues': []
        }
        
        for artifact in self.artifacts.values():
            if artifact.validation_results:
                latest_validation = artifact.validation_results[-1]
                if latest_validation.get('valid', False):
                    results['valid'] += 1
                else:
                    results['invalid'] += 1
                    results['issues'].append({
                        'artifact_id': artifact.id,
                        'name': artifact.name,
                        'issues': latest_validation.get('issues', [])
                    })
            else:
                results['invalid'] += 1
                results['issues'].append({
                    'artifact_id': artifact.id,
                    'name': artifact.name,
                    'issues': ['No validation results']
                })
                
        return results