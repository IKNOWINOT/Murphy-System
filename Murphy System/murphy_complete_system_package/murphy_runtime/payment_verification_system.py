# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Payment Verification & Sales Tracking
Verifies payments before allowing artifact downloads
Tracks all sales and customer purchases
"""

import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
import hashlib
import secrets

logger = logging.getLogger(__name__)


class PaymentVerificationSystem:
    """Verify payments and track sales"""
    
    def __init__(self):
        self.sales = []  # In production, this would be in database
        self.customers = {}  # customer_email -> list of purchases
        self.payment_tokens = {}  # token -> sale_id
        
    def create_sale(self, product_id: str, customer_email: str, amount: float, 
                    payment_provider: str, payment_id: str = None) -> Dict:
        """Create a new sale record"""
        
        sale_id = f"sale_{len(self.sales) + 1}_{secrets.token_hex(8)}"
        download_token = secrets.token_urlsafe(32)
        
        sale = {
            'sale_id': sale_id,
            'product_id': product_id,
            'customer_email': customer_email,
            'amount': amount,
            'payment_provider': payment_provider,
            'payment_id': payment_id or f"{payment_provider}_{secrets.token_hex(8)}",
            'payment_status': 'pending',  # pending, completed, failed, refunded
            'download_token': download_token,
            'download_count': 0,
            'download_limit': 5,  # Allow 5 downloads
            'created_at': datetime.now().isoformat(),
            'paid_at': None,
            'expires_at': None  # For time-limited access
        }
        
        self.sales.append(sale)
        self.payment_tokens[download_token] = sale_id
        
        # Track customer purchases
        if customer_email not in self.customers:
            self.customers[customer_email] = []
        self.customers[customer_email].append(sale_id)
        
        logger.info(f"✓ Created sale: {sale_id} for {customer_email}")
        
        return sale
    
    def verify_payment(self, sale_id: str, payment_provider: str, 
                      payment_id: str) -> Dict:
        """Verify payment with payment provider"""
        
        sale = self.get_sale(sale_id)
        if not sale:
            return {
                'success': False,
                'error': 'Sale not found'
            }
        
        # In production, this would call the payment provider API
        # For now, we'll simulate verification
        
        if payment_provider == 'paypal':
            verified = self._verify_paypal_payment(payment_id)
        elif payment_provider == 'square':
            verified = self._verify_square_payment(payment_id)
        elif payment_provider == 'coinbase':
            verified = self._verify_coinbase_payment(payment_id)
        elif payment_provider == 'paddle':
            verified = self._verify_paddle_payment(payment_id)
        elif payment_provider == 'lemonsqueezy':
            verified = self._verify_lemonsqueezy_payment(payment_id)
        else:
            return {
                'success': False,
                'error': f'Unsupported payment provider: {payment_provider}'
            }
        
        if verified:
            sale['payment_status'] = 'completed'
            sale['paid_at'] = datetime.now().isoformat()
            
            logger.info(f"✓ Payment verified for sale: {sale_id}")
            
            return {
                'success': True,
                'sale_id': sale_id,
                'download_token': sale['download_token'],
                'message': 'Payment verified successfully'
            }
        else:
            sale['payment_status'] = 'failed'
            return {
                'success': False,
                'error': 'Payment verification failed'
            }
    
    def _verify_paypal_payment(self, payment_id: str) -> bool:
        """Verify PayPal payment (production would call PayPal API)"""
        # In production: Call PayPal API to verify payment
        # For demo: Accept any payment_id
        logger.info(f"Verifying PayPal payment: {payment_id}")
        return True  # Demo mode
    
    def _verify_square_payment(self, payment_id: str) -> bool:
        """Verify Square payment (production would call Square API)"""
        logger.info(f"Verifying Square payment: {payment_id}")
        return True  # Demo mode
    
    def _verify_coinbase_payment(self, payment_id: str) -> bool:
        """Verify Coinbase payment (production would call Coinbase API)"""
        logger.info(f"Verifying Coinbase payment: {payment_id}")
        return True  # Demo mode
    
    def _verify_paddle_payment(self, payment_id: str) -> bool:
        """Verify Paddle payment (production would call Paddle API)"""
        logger.info(f"Verifying Paddle payment: {payment_id}")
        return True  # Demo mode
    
    def _verify_lemonsqueezy_payment(self, payment_id: str) -> bool:
        """Verify Lemon Squeezy payment (production would call API)"""
        logger.info(f"Verifying Lemon Squeezy payment: {payment_id}")
        return True  # Demo mode
    
    def check_download_access(self, download_token: str) -> Dict:
        """Check if customer can download artifact"""
        
        if download_token not in self.payment_tokens:
            return {
                'success': False,
                'error': 'Invalid download token'
            }
        
        sale_id = self.payment_tokens[download_token]
        sale = self.get_sale(sale_id)
        
        if not sale:
            return {
                'success': False,
                'error': 'Sale not found'
            }
        
        # Check payment status
        if sale['payment_status'] != 'completed':
            return {
                'success': False,
                'error': 'Payment not completed',
                'payment_status': sale['payment_status']
            }
        
        # Check download limit
        if sale['download_count'] >= sale['download_limit']:
            return {
                'success': False,
                'error': 'Download limit reached',
                'download_count': sale['download_count'],
                'download_limit': sale['download_limit']
            }
        
        # Check expiration (if set)
        if sale.get('expires_at'):
            expires = datetime.fromisoformat(sale['expires_at'])
            if datetime.now() > expires:
                return {
                    'success': False,
                    'error': 'Download link expired',
                    'expired_at': sale['expires_at']
                }
        
        return {
            'success': True,
            'sale_id': sale_id,
            'product_id': sale['product_id'],
            'customer_email': sale['customer_email'],
            'downloads_remaining': sale['download_limit'] - sale['download_count']
        }
    
    def record_download(self, download_token: str) -> Dict:
        """Record that a download occurred"""
        
        access_check = self.check_download_access(download_token)
        if not access_check['success']:
            return access_check
        
        sale_id = self.payment_tokens[download_token]
        sale = self.get_sale(sale_id)
        
        sale['download_count'] += 1
        sale['last_download_at'] = datetime.now().isoformat()
        
        logger.info(f"✓ Download recorded for sale: {sale_id} (count: {sale['download_count']})")
        
        return {
            'success': True,
            'sale_id': sale_id,
            'download_count': sale['download_count'],
            'downloads_remaining': sale['download_limit'] - sale['download_count']
        }
    
    def get_sale(self, sale_id: str) -> Optional[Dict]:
        """Get sale by ID"""
        for sale in self.sales:
            if sale['sale_id'] == sale_id:
                return sale
        return None
    
    def get_customer_purchases(self, customer_email: str) -> List[Dict]:
        """Get all purchases for a customer"""
        if customer_email not in self.customers:
            return []
        
        sale_ids = self.customers[customer_email]
        return [self.get_sale(sid) for sid in sale_ids if self.get_sale(sid)]
    
    def get_all_sales(self, status: str = None) -> List[Dict]:
        """Get all sales, optionally filtered by status"""
        if status:
            return [s for s in self.sales if s['payment_status'] == status]
        return self.sales
    
    def get_sales_stats(self) -> Dict:
        """Get sales statistics"""
        total_sales = len(self.sales)
        completed_sales = len([s for s in self.sales if s['payment_status'] == 'completed'])
        pending_sales = len([s for s in self.sales if s['payment_status'] == 'pending'])
        failed_sales = len([s for s in self.sales if s['payment_status'] == 'failed'])
        
        total_revenue = sum(s['amount'] for s in self.sales if s['payment_status'] == 'completed')
        
        return {
            'total_sales': total_sales,
            'completed_sales': completed_sales,
            'pending_sales': pending_sales,
            'failed_sales': failed_sales,
            'total_revenue': total_revenue,
            'total_customers': len(self.customers),
            'average_order_value': total_revenue / completed_sales if completed_sales > 0 else 0
        }
    
    def refund_sale(self, sale_id: str, reason: str = None) -> Dict:
        """Process a refund"""
        sale = self.get_sale(sale_id)
        if not sale:
            return {
                'success': False,
                'error': 'Sale not found'
            }
        
        if sale['payment_status'] != 'completed':
            return {
                'success': False,
                'error': 'Can only refund completed payments'
            }
        
        sale['payment_status'] = 'refunded'
        sale['refunded_at'] = datetime.now().isoformat()
        sale['refund_reason'] = reason
        
        logger.info(f"✓ Refunded sale: {sale_id}")
        
        return {
            'success': True,
            'sale_id': sale_id,
            'refunded_amount': sale['amount'],
            'message': 'Refund processed successfully'
        }


# Global instance
_payment_verification = None

def get_payment_verification() -> PaymentVerificationSystem:
    """Get or create payment verification instance"""
    global _payment_verification
    if _payment_verification is None:
        _payment_verification = PaymentVerificationSystem()
    return _payment_verification