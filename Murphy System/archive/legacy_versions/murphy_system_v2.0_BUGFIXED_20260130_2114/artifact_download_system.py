"""
Murphy System - Artifact Download with Payment Verification
Allows customers to download artifacts only after payment verification
"""

import os
import logging
from typing import Dict, Optional
from flask import send_file, send_from_directory
from datetime import datetime
import mimetypes

logger = logging.getLogger(__name__)


class ArtifactDownloadSystem:
    """Manage artifact downloads with payment verification"""
    
    def __init__(self, payment_verification, artifact_manager=None):
        self.payment_verification = payment_verification
        self.artifact_manager = artifact_manager
        self.download_directory = "/workspace"  # Base directory for artifacts
        
    def get_download_url(self, product_id: str, sale_id: str) -> Dict:
        """Generate download URL for a product"""
        
        # Get sale information
        sale = self.payment_verification.get_sale(sale_id)
        
        if not sale:
            return {
                'success': False,
                'error': 'Sale not found'
            }
        
        # Verify product matches
        if sale['product_id'] != product_id:
            return {
                'success': False,
                'error': 'Product does not match sale'
            }
        
        # Check payment status
        if sale['payment_status'] != 'completed':
            return {
                'success': False,
                'error': 'Payment not completed',
                'payment_status': sale['payment_status'],
                'message': 'Please complete payment before downloading'
            }
        
        # Generate download URL with token
        download_token = sale['download_token']
        download_url = f"/api/download/{download_token}"
        
        return {
            'success': True,
            'download_url': download_url,
            'download_token': download_token,
            'product_id': product_id,
            'downloads_remaining': sale['download_limit'] - sale['download_count'],
            'expires_at': sale.get('expires_at')
        }
    
    def download_artifact(self, download_token: str) -> Dict:
        """Download artifact with payment verification"""
        
        # Check download access
        access_check = self.payment_verification.check_download_access(download_token)
        
        if not access_check['success']:
            return access_check
        
        product_id = access_check['product_id']
        
        # Find artifact file
        artifact_file = self._find_artifact_file(product_id)
        
        if not artifact_file:
            return {
                'success': False,
                'error': 'Artifact file not found',
                'product_id': product_id
            }
        
        # Record download
        download_record = self.payment_verification.record_download(download_token)
        
        if not download_record['success']:
            return download_record
        
        # Return file information for download
        return {
            'success': True,
            'file_path': artifact_file,
            'product_id': product_id,
            'download_count': download_record['download_count'],
            'downloads_remaining': download_record['downloads_remaining'],
            'customer_email': access_check['customer_email']
        }
    
    def _find_artifact_file(self, product_id: str) -> Optional[str]:
        """Find artifact file for product"""
        
        # Search for files matching product_id
        # In production, this would query the database
        
        # Common patterns for artifact files
        patterns = [
            f"{product_id}.txt",
            f"{product_id}.pdf",
            f"{product_id}.zip",
            f"{product_id}_textbook.txt",
            f"{product_id}_course.zip"
        ]
        
        for pattern in patterns:
            file_path = os.path.join(self.download_directory, pattern)
            if os.path.exists(file_path):
                return file_path
        
        # Try to find by searching for files with product_id in name
        try:
            for filename in os.listdir(self.download_directory):
                if product_id in filename and not filename.endswith('.html'):
                    file_path = os.path.join(self.download_directory, filename)
                    if os.path.isfile(file_path):
                        return file_path
        except Exception as e:
            logger.error(f"Error searching for artifact: {e}")
        
        return None
    
    def list_customer_downloads(self, customer_email: str) -> Dict:
        """List all available downloads for a customer"""
        
        purchases = self.payment_verification.get_customer_purchases(customer_email)
        
        downloads = []
        for sale in purchases:
            if sale['payment_status'] == 'completed':
                artifact_file = self._find_artifact_file(sale['product_id'])
                
                downloads.append({
                    'product_id': sale['product_id'],
                    'sale_id': sale['sale_id'],
                    'download_token': sale['download_token'],
                    'download_url': f"/api/download/{sale['download_token']}",
                    'downloads_used': sale['download_count'],
                    'downloads_remaining': sale['download_limit'] - sale['download_count'],
                    'purchased_at': sale['paid_at'],
                    'artifact_available': artifact_file is not None,
                    'artifact_file': os.path.basename(artifact_file) if artifact_file else None
                })
        
        return {
            'success': True,
            'customer_email': customer_email,
            'downloads': downloads,
            'total_purchases': len(purchases),
            'available_downloads': len(downloads)
        }
    
    def get_artifact_info(self, product_id: str) -> Dict:
        """Get information about an artifact"""
        
        artifact_file = self._find_artifact_file(product_id)
        
        if not artifact_file:
            return {
                'success': False,
                'error': 'Artifact not found',
                'product_id': product_id
            }
        
        # Get file information
        file_size = os.path.getsize(artifact_file)
        file_name = os.path.basename(artifact_file)
        mime_type, _ = mimetypes.guess_type(artifact_file)
        
        return {
            'success': True,
            'product_id': product_id,
            'file_name': file_name,
            'file_size': file_size,
            'file_size_mb': round(file_size / (1024 * 1024), 2),
            'mime_type': mime_type or 'application/octet-stream',
            'file_path': artifact_file
        }
    
    def create_download_package(self, product_id: str, files: list) -> Dict:
        """Create a downloadable package (zip) of multiple files"""
        
        import zipfile
        
        package_name = f"{product_id}_package.zip"
        package_path = os.path.join(self.download_directory, package_name)
        
        try:
            with zipfile.ZipFile(package_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in files:
                    if os.path.exists(file_path):
                        arcname = os.path.basename(file_path)
                        zipf.write(file_path, arcname)
            
            logger.info(f"✓ Created download package: {package_name}")
            
            return {
                'success': True,
                'package_path': package_path,
                'package_name': package_name,
                'files_included': len(files)
            }
            
        except Exception as e:
            logger.error(f"Error creating package: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def verify_and_download(self, download_token: str, customer_email: str = None) -> Dict:
        """Verify payment and prepare download"""
        
        # Check download access
        access_check = self.payment_verification.check_download_access(download_token)
        
        if not access_check['success']:
            return access_check
        
        # Verify customer email if provided
        if customer_email and access_check['customer_email'] != customer_email:
            return {
                'success': False,
                'error': 'Customer email does not match'
            }
        
        # Get artifact
        return self.download_artifact(download_token)
    
    def get_download_stats(self) -> Dict:
        """Get download statistics"""
        
        all_sales = self.payment_verification.get_all_sales(status='completed')
        
        total_downloads = sum(sale['download_count'] for sale in all_sales)
        products_with_downloads = len(set(sale['product_id'] for sale in all_sales if sale['download_count'] > 0))
        
        return {
            'success': True,
            'total_completed_sales': len(all_sales),
            'total_downloads': total_downloads,
            'products_with_downloads': products_with_downloads,
            'average_downloads_per_sale': total_downloads / len(all_sales) if all_sales else 0
        }


# Global instance
_artifact_download_system = None

def get_artifact_download_system(payment_verification, artifact_manager=None) -> ArtifactDownloadSystem:
    """Get or create artifact download system instance"""
    global _artifact_download_system
    if _artifact_download_system is None:
        _artifact_download_system = ArtifactDownloadSystem(
            payment_verification=payment_verification,
            artifact_manager=artifact_manager
        )
    return _artifact_download_system