# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Business Automation Integrations
Payment processing, email marketing, and social media automation
NO STRIPE - Using PayPal, Square, and Crypto alternatives
"""

import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class PaymentProcessor:
    """Handle payment processing via multiple providers (NO STRIPE)"""
    
    def __init__(self, provider='paypal', api_key=None, api_secret=None):
        """
        Initialize payment processor
        
        Supported providers:
        - paypal: PayPal Commerce Platform
        - square: Square Payment API
        - coinbase: Coinbase Commerce (crypto)
        - paddle: Paddle (SaaS billing)
        - lemonsqueezy: Lemon Squeezy (merchant of record)
        """
        self.provider = provider
        self.api_key = api_key or os.getenv(f'{provider.upper()}_API_KEY')
        self.api_secret = api_secret or os.getenv(f'{provider.upper()}_API_SECRET')
        
        self.provider_urls = {
            'paypal': 'https://api-m.paypal.com',
            'square': 'https://connect.squareup.com',
            'coinbase': 'https://api.commerce.coinbase.com',
            'paddle': 'https://vendors.paddle.com/api',
            'lemonsqueezy': 'https://api.lemonsqueezy.com/v1'
        }
        
        self.base_url = self.provider_urls.get(provider)
    
    def create_payment_link(self, product_name: str, price: float, description: str, currency: str = 'USD') -> Dict:
        """Create a payment link for the product"""
        
        if not self.api_key:
            return {
                'success': False,
                'error': f'{self.provider.title()} API key not configured',
                'demo_link': f'https://demo.{self.provider}.com/buy/{product_name.replace(" ", "-")}',
                'provider': self.provider
            }
        
        # Generate payment link based on provider
        if self.provider == 'paypal':
            return self._create_paypal_link(product_name, price, description, currency)
        elif self.provider == 'square':
            return self._create_square_link(product_name, price, description, currency)
        elif self.provider == 'coinbase':
            return self._create_coinbase_link(product_name, price, description)
        elif self.provider == 'paddle':
            return self._create_paddle_link(product_name, price, description, currency)
        elif self.provider == 'lemonsqueezy':
            return self._create_lemonsqueezy_link(product_name, price, description, currency)
        else:
            return {
                'success': False,
                'error': f'Unsupported payment provider: {self.provider}'
            }
    
    def _create_paypal_link(self, product_name: str, price: float, description: str, currency: str) -> Dict:
        """Create PayPal payment link"""
        # In production, this would call PayPal API to create a payment button/link
        product_id = product_name.replace(" ", "-").lower()
        return {
            'success': True,
            'provider': 'paypal',
            'payment_link': f'https://www.paypal.com/paypalme/yourbusiness/{price}',
            'checkout_link': f'https://www.paypal.com/checkoutnow?token={product_id}',
            'product': product_name,
            'price': price,
            'currency': currency,
            'description': description,
            'integration_type': 'PayPal Commerce Platform'
        }
    
    def _create_square_link(self, product_name: str, price: float, description: str, currency: str) -> Dict:
        """Create Square payment link"""
        # In production, this would call Square API
        product_id = product_name.replace(" ", "-").lower()
        return {
            'success': True,
            'provider': 'square',
            'payment_link': f'https://square.link/{product_id}',
            'checkout_link': f'https://checkout.square.site/{product_id}',
            'product': product_name,
            'price': price,
            'currency': currency,
            'description': description,
            'integration_type': 'Square Online Checkout'
        }
    
    def _create_coinbase_link(self, product_name: str, price: float, description: str) -> Dict:
        """Create Coinbase Commerce crypto payment link"""
        # In production, this would call Coinbase Commerce API
        product_id = product_name.replace(" ", "-").lower()
        return {
            'success': True,
            'provider': 'coinbase',
            'payment_link': f'https://commerce.coinbase.com/charges/{product_id}',
            'product': product_name,
            'price': price,
            'currency': 'USD',
            'crypto_accepted': ['BTC', 'ETH', 'USDC', 'DAI'],
            'description': description,
            'integration_type': 'Coinbase Commerce'
        }
    
    def _create_paddle_link(self, product_name: str, price: float, description: str, currency: str) -> Dict:
        """Create Paddle payment link"""
        # In production, this would call Paddle API
        product_id = product_name.replace(" ", "-").lower()
        return {
            'success': True,
            'provider': 'paddle',
            'payment_link': f'https://buy.paddle.com/product/{product_id}',
            'product': product_name,
            'price': price,
            'currency': currency,
            'description': description,
            'integration_type': 'Paddle Checkout',
            'features': ['Merchant of Record', 'Global Tax Handling', 'Subscription Management']
        }
    
    def _create_lemonsqueezy_link(self, product_name: str, price: float, description: str, currency: str) -> Dict:
        """Create Lemon Squeezy payment link"""
        # In production, this would call Lemon Squeezy API
        product_id = product_name.replace(" ", "-").lower()
        return {
            'success': True,
            'provider': 'lemonsqueezy',
            'payment_link': f'https://yourbusiness.lemonsqueezy.com/checkout/buy/{product_id}',
            'product': product_name,
            'price': price,
            'currency': currency,
            'description': description,
            'integration_type': 'Lemon Squeezy',
            'features': ['Merchant of Record', 'EU VAT Handling', 'Fraud Prevention']
        }
    
    def create_product(self, name: str, price: float, description: str, currency: str = 'USD') -> Dict:
        """Create a product in the payment system"""
        return {
            'success': True,
            'provider': self.provider,
            'product_id': f'prod_{name.replace(" ", "_")}_{self.provider}',
            'name': name,
            'price': price,
            'currency': currency,
            'description': description,
            'created_at': datetime.now().isoformat()
        }
    
    def get_supported_providers(self) -> List[str]:
        """Get list of supported payment providers"""
        return list(self.provider_urls.keys())


class EmailMarketing:
    """Handle email marketing campaigns"""
    
    def __init__(self, smtp_host=None, smtp_port=None, smtp_user=None, smtp_pass=None):
        self.smtp_host = smtp_host or os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = smtp_port or int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = smtp_user or os.getenv('SMTP_USER')
        self.smtp_pass = smtp_pass or os.getenv('SMTP_PASS')
    
    def send_email(self, to_email: str, subject: str, body: str, html: bool = False) -> Dict:
        """Send an email"""
        if not self.smtp_user or not self.smtp_pass:
            return {
                'success': False,
                'error': 'SMTP credentials not configured',
                'demo': True,
                'message': f'Would send email to {to_email}: {subject}'
            }
        
        # In production, this would actually send the email
        return {
            'success': True,
            'to': to_email,
            'subject': subject,
            'sent_at': datetime.now().isoformat()
        }
    
    def create_campaign(self, name: str, subject: str, body: str, recipients: List[str]) -> Dict:
        """Create an email marketing campaign"""
        return {
            'success': True,
            'campaign_id': f'camp_{name.replace(" ", "_")}',
            'name': name,
            'subject': subject,
            'recipients': len(recipients),
            'status': 'draft',
            'created_at': datetime.now().isoformat()
        }
    
    def send_campaign(self, campaign_id: str) -> Dict:
        """Send a marketing campaign"""
        return {
            'success': True,
            'campaign_id': campaign_id,
            'status': 'sent',
            'sent_at': datetime.now().isoformat()
        }


class SocialMediaManager:
    """Manage social media posting and engagement"""
    
    def __init__(self):
        self.twitter_api_key = os.getenv('TWITTER_API_KEY')
        self.linkedin_api_key = os.getenv('LINKEDIN_API_KEY')
        self.facebook_api_key = os.getenv('FACEBOOK_API_KEY')
    
    def post_to_twitter(self, content: str, media_urls: List[str] = None) -> Dict:
        """Post to Twitter/X"""
        if not self.twitter_api_key:
            return {
                'success': False,
                'error': 'Twitter API key not configured',
                'demo': True,
                'message': f'Would post to Twitter: {content[:50]}...'
            }
        
        return {
            'success': True,
            'platform': 'twitter',
            'post_id': f'tweet_{datetime.now().timestamp()}',
            'content': content,
            'posted_at': datetime.now().isoformat()
        }
    
    def post_to_linkedin(self, content: str, media_urls: List[str] = None) -> Dict:
        """Post to LinkedIn"""
        if not self.linkedin_api_key:
            return {
                'success': False,
                'error': 'LinkedIn API key not configured',
                'demo': True,
                'message': f'Would post to LinkedIn: {content[:50]}...'
            }
        
        return {
            'success': True,
            'platform': 'linkedin',
            'post_id': f'li_{datetime.now().timestamp()}',
            'content': content,
            'posted_at': datetime.now().isoformat()
        }
    
    def post_to_facebook(self, content: str, media_urls: List[str] = None) -> Dict:
        """Post to Facebook"""
        if not self.facebook_api_key:
            return {
                'success': False,
                'error': 'Facebook API key not configured',
                'demo': True,
                'message': f'Would post to Facebook: {content[:50]}...'
            }
        
        return {
            'success': True,
            'platform': 'facebook',
            'post_id': f'fb_{datetime.now().timestamp()}',
            'content': content,
            'posted_at': datetime.now().isoformat()
        }
    
    def schedule_post(self, platform: str, content: str, scheduled_time: str) -> Dict:
        """Schedule a social media post"""
        return {
            'success': True,
            'platform': platform,
            'content': content,
            'scheduled_for': scheduled_time,
            'status': 'scheduled'
        }


class BusinessAutomation:
    """Complete business automation orchestrator"""
    
    def __init__(self, llm_manager=None, payment_provider='paypal'):
        self.llm_manager = llm_manager
        self.payment_processor = PaymentProcessor(provider=payment_provider)
        self.email_marketing = EmailMarketing()
        self.social_media = SocialMediaManager()
        self.products = []
        self.customers = []
        self.campaigns = []
    
    def create_autonomous_textbook(self, topic: str, title: str, price: float, 
                                   payment_provider: str = None) -> Dict:
        """
        Autonomously create a complete textbook business:
        1. Generate textbook content using LLM
        2. Create professional sales website
        3. Setup payment processing (NO STRIPE)
        4. Prepare marketing materials
        """
        
        # Use specified provider or default
        if payment_provider:
            self.payment_processor = PaymentProcessor(provider=payment_provider)
        
        logger.info(f"Creating autonomous textbook business: {title}")
        logger.info(f"Payment provider: {self.payment_processor.provider}")
        
        # Step 1: Generate textbook content
        if self.llm_manager:
            textbook_prompt = f"""Write a comprehensive textbook on {topic}.
            
Title: {title}

Create a complete textbook with:
- Introduction explaining the importance of {topic}
- 10 detailed chapters covering all aspects
- Practical examples and exercises
- Summary and conclusion
- References and further reading

Make it professional, educational, and valuable."""
            
            textbook_content = self.llm_manager.generate(
                prompt=textbook_prompt,
                max_tokens=4000
            )
        else:
            textbook_content = f"[Demo Mode] Complete textbook on {topic} would be generated here."
        
        # Step 2: Create sales website
        sales_website = self._generate_sales_website(title, topic, price, textbook_content)
        
        # Step 3: Setup payment processing
        payment_info = self.payment_processor.create_payment_link(
            product_name=title,
            price=price,
            description=f"Complete guide to {topic}"
        )
        
        # Step 4: Prepare marketing materials
        marketing_content = self._generate_marketing_content(title, topic, price)
        
        # Save textbook
        textbook_filename = f"{title.replace(' ', '_')}.txt"
        with open(textbook_filename, 'w') as f:
            f.write(textbook_content)
        
        # Save sales website
        website_filename = f"{title.replace(' ', '_')}_sales.html"
        with open(website_filename, 'w') as f:
            f.write(sales_website)
        
        # Store product
        product = {
            'id': f'prod_{len(self.products) + 1}',
            'title': title,
            'topic': topic,
            'price': price,
            'payment_provider': self.payment_processor.provider,
            'payment_info': payment_info,
            'textbook_file': textbook_filename,
            'website_file': website_filename,
            'marketing': marketing_content,
            'created_at': datetime.now().isoformat()
        }
        
        self.products.append(product)
        
        return {
            'success': True,
            'product': product,
            'files_created': [textbook_filename, website_filename],
            'payment_provider': self.payment_processor.provider,
            'next_steps': [
                f'Review textbook: {textbook_filename}',
                f'Review sales page: {website_filename}',
                f'Configure {self.payment_processor.provider.title()} API keys',
                'Launch marketing campaign'
            ]
        }
    
    def _generate_sales_website(self, title: str, topic: str, price: float, content_preview: str) -> str:
        """Generate a professional sales website"""
        
        preview = content_preview[:500] if len(content_preview) > 500 else content_preview
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Professional Guide</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; }}
        .hero {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 100px 20px; text-align: center; }}
        .hero h1 {{ font-size: 3em; margin-bottom: 20px; }}
        .hero p {{ font-size: 1.3em; margin-bottom: 30px; }}
        .cta-button {{ background: #ff6b6b; color: white; padding: 15px 40px; font-size: 1.2em; border: none; border-radius: 50px; cursor: pointer; text-decoration: none; display: inline-block; }}
        .cta-button:hover {{ background: #ff5252; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 60px 20px; }}
        .features {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 30px; margin: 60px 0; }}
        .feature {{ background: #f8f9fa; padding: 30px; border-radius: 10px; }}
        .feature h3 {{ color: #667eea; margin-bottom: 15px; }}
        .price {{ text-align: center; font-size: 3em; color: #667eea; margin: 40px 0; }}
        .preview {{ background: #f8f9fa; padding: 30px; border-radius: 10px; margin: 40px 0; }}
        footer {{ background: #333; color: white; text-align: center; padding: 30px; }}
    </style>
</head>
<body>
    <div class="hero">
        <h1>{title}</h1>
        <p>Master {topic} with this comprehensive professional guide</p>
        <a href="#buy" class="cta-button">Get Started Now - ${price}</a>
    </div>
    
    <div class="container">
        <h2>What You'll Learn</h2>
        <div class="features">
            <div class="feature">
                <h3>📚 Comprehensive Coverage</h3>
                <p>10 detailed chapters covering every aspect of {topic}</p>
            </div>
            <div class="feature">
                <h3>💡 Practical Examples</h3>
                <p>Real-world examples and hands-on exercises</p>
            </div>
            <div class="feature">
                <h3>🎯 Expert Knowledge</h3>
                <p>Professional insights and best practices</p>
            </div>
            <div class="feature">
                <h3>📖 Easy to Follow</h3>
                <p>Clear explanations suitable for all levels</p>
            </div>
            <div class="feature">
                <h3>🚀 Immediate Access</h3>
                <p>Download instantly after purchase</p>
            </div>
            <div class="feature">
                <h3>💯 Complete Guide</h3>
                <p>Everything you need to master {topic}</p>
            </div>
        </div>
        
        <div class="preview">
            <h2>Preview</h2>
            <p>{preview}...</p>
        </div>
        
        <div id="buy" style="text-align: center;">
            <div class="price">${price}</div>
            <a href="#" class="cta-button">Buy Now</a>
            <p style="margin-top: 20px; color: #666;">Secure payment processing • Instant download • 30-day guarantee</p>
        </div>
    </div>
    
    <footer>
        <p>&copy; 2024 {title}. All rights reserved.</p>
        <p>Powered by Murphy Autonomous Business System</p>
    </footer>
</body>
</html>"""
        
        return html
    
    def _generate_marketing_content(self, title: str, topic: str, price: float) -> Dict:
        """Generate marketing content for social media and email"""
        
        return {
            'email_subject': f"New Release: {title}",
            'email_body': f"We're excited to announce our new comprehensive guide: {title}!\n\nLearn everything about {topic} with our professional textbook.\n\nSpecial launch price: ${price}\n\nGet your copy today!",
            'twitter_post': f"🚀 Just released: {title}! Master {topic} with our comprehensive guide. ${price} - Get it now!",
            'linkedin_post': f"Excited to share our latest educational resource: {title}. A complete professional guide to {topic}. Perfect for anyone looking to deepen their knowledge. Available now for ${price}.",
            'facebook_post': f"📚 NEW RELEASE 📚\n\n{title}\n\nYour complete guide to {topic}!\n\n✅ 10 comprehensive chapters\n✅ Practical examples\n✅ Expert insights\n\nOnly ${price} - Limited time offer!"
        }
    
    def get_products(self) -> List[Dict]:
        """Get all products"""
        return self.products
    
    def get_product(self, product_id: str) -> Optional[Dict]:
        """Get specific product"""
        for product in self.products:
            if product['id'] == product_id:
                return product
        return None


# Global instance
_business_automation = None

def get_business_automation(llm_manager=None, payment_provider='paypal') -> BusinessAutomation:
    """Get or create business automation instance"""
    global _business_automation
    if _business_automation is None:
        _business_automation = BusinessAutomation(llm_manager=llm_manager, payment_provider=payment_provider)
    return _business_automation