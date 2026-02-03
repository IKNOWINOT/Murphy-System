# Murphy System - Payment Providers Guide

## 🚫 NO STRIPE - Better Alternatives Available!

We've replaced Stripe with 5 superior payment processing options, each with unique advantages.

---

## 💳 Supported Payment Providers

### 1. PayPal Commerce Platform
**Best for: Most businesses, global reach**

```bash
/business.payment.setup paypal
```

**Advantages:**
- ✅ Most recognized payment brand worldwide
- ✅ 400+ million active users
- ✅ Buyer and seller protection
- ✅ No monthly fees
- ✅ Accept credit cards without merchant account
- ✅ PayPal.me links for quick payments
- ✅ One-click checkout for PayPal users

**Fees:**
- 2.9% + $0.30 per transaction (US)
- International: 4.4% + fixed fee

**API Keys Needed:**
- `PAYPAL_API_KEY`
- `PAYPAL_API_SECRET`

**Integration:**
```python
payment_processor = PaymentProcessor(provider='paypal')
result = payment_processor.create_payment_link(
    product_name="My Product",
    price=29.99,
    description="Product description"
)
```

---

### 2. Square Payment API
**Best for: Small businesses, in-person + online**

```bash
/business.payment.setup square
```

**Advantages:**
- ✅ Unified platform (online + in-person)
- ✅ Free POS software
- ✅ Next-day deposits
- ✅ No monthly fees
- ✅ Built-in inventory management
- ✅ Square Online store included
- ✅ Great for retail + e-commerce combo

**Fees:**
- 2.9% + $0.30 per online transaction
- 2.6% + $0.10 per in-person transaction

**API Keys Needed:**
- `SQUARE_API_KEY`
- `SQUARE_API_SECRET`

**Integration:**
```python
payment_processor = PaymentProcessor(provider='square')
result = payment_processor.create_payment_link(
    product_name="My Product",
    price=29.99,
    description="Product description"
)
```

---

### 3. Coinbase Commerce (Cryptocurrency)
**Best for: Crypto payments, global customers**

```bash
/business.payment.setup coinbase
```

**Advantages:**
- ✅ Accept Bitcoin, Ethereum, USDC, DAI
- ✅ No chargebacks (crypto is final)
- ✅ Lower fees than credit cards
- ✅ Global reach without currency conversion
- ✅ Instant settlement
- ✅ No middleman
- ✅ Appeals to crypto-native customers

**Fees:**
- 1% per transaction
- No monthly fees

**Supported Cryptocurrencies:**
- Bitcoin (BTC)
- Ethereum (ETH)
- USD Coin (USDC)
- Dai (DAI)
- Litecoin (LTC)
- Bitcoin Cash (BCH)

**API Keys Needed:**
- `COINBASE_API_KEY`

**Integration:**
```python
payment_processor = PaymentProcessor(provider='coinbase')
result = payment_processor.create_payment_link(
    product_name="My Product",
    price=29.99,
    description="Product description"
)
# Returns crypto payment link accepting BTC, ETH, USDC, DAI
```

---

### 4. Paddle (Merchant of Record)
**Best for: SaaS, digital products, global sales**

```bash
/business.payment.setup paddle
```

**Advantages:**
- ✅ **Merchant of Record** - Paddle handles all tax compliance
- ✅ Automatic global tax calculation and remittance
- ✅ EU VAT, US sales tax, GST handled automatically
- ✅ Subscription management built-in
- ✅ Fraud prevention included
- ✅ Multi-currency support
- ✅ You focus on product, Paddle handles compliance

**Fees:**
- 5% + $0.50 per transaction (includes tax handling)
- No monthly fees

**Perfect For:**
- SaaS businesses
- Digital products
- Subscription services
- Global sales without tax headaches

**API Keys Needed:**
- `PADDLE_API_KEY`
- `PADDLE_API_SECRET`

**Integration:**
```python
payment_processor = PaymentProcessor(provider='paddle')
result = payment_processor.create_payment_link(
    product_name="My SaaS Product",
    price=29.99,
    description="Monthly subscription"
)
# Paddle handles all tax compliance automatically
```

---

### 5. Lemon Squeezy (Merchant of Record)
**Best for: Digital products, EU compliance, indie makers**

```bash
/business.payment.setup lemonsqueezy
```

**Advantages:**
- ✅ **Merchant of Record** - Full tax compliance
- ✅ EU VAT MOSS compliant
- ✅ Fraud prevention and detection
- ✅ Beautiful checkout experience
- ✅ Subscription management
- ✅ License key generation
- ✅ Affiliate program built-in
- ✅ Popular with indie makers

**Fees:**
- 5% + $0.50 per transaction (includes tax handling)
- No monthly fees

**Perfect For:**
- Digital downloads
- Software licenses
- Online courses
- E-books
- Indie products

**API Keys Needed:**
- `LEMONSQUEEZY_API_KEY`

**Integration:**
```python
payment_processor = PaymentProcessor(provider='lemonsqueezy')
result = payment_processor.create_payment_link(
    product_name="My Digital Product",
    price=29.99,
    description="E-book download"
)
# Lemon Squeezy handles EU VAT and fraud prevention
```

---

## 🎯 Which Provider Should You Choose?

### Choose **PayPal** if:
- You want maximum customer trust
- You need global reach
- You want buyer/seller protection
- You're just starting out

### Choose **Square** if:
- You have both online and in-person sales
- You need POS + e-commerce
- You want free inventory management
- You're a small retail business

### Choose **Coinbase** if:
- You want to accept cryptocurrency
- You want lower fees (1%)
- You want no chargebacks
- Your customers are crypto-savvy

### Choose **Paddle** if:
- You're selling SaaS or subscriptions
- You want automatic tax compliance
- You sell globally
- You don't want to deal with VAT/tax

### Choose **Lemon Squeezy** if:
- You're an indie maker
- You sell digital products
- You need EU VAT compliance
- You want affiliate program built-in

---

## 📊 Fee Comparison

| Provider | Transaction Fee | Monthly Fee | Tax Handling | Best For |
|----------|----------------|-------------|--------------|----------|
| **PayPal** | 2.9% + $0.30 | $0 | Manual | General use |
| **Square** | 2.9% + $0.30 | $0 | Manual | Retail + online |
| **Coinbase** | 1% | $0 | N/A | Crypto payments |
| **Paddle** | 5% + $0.50 | $0 | **Automatic** | SaaS, global |
| **Lemon Squeezy** | 5% + $0.50 | $0 | **Automatic** | Digital products |

---

## 🚀 Quick Start Examples

### Example 1: Create Product with PayPal
```bash
# Setup PayPal
/business.payment.setup paypal

# Create product
/business.product.create textbook "AI Automation Guide" 39.99

# Result: Product with PayPal payment link
```

### Example 2: Create Product with Crypto Payments
```bash
# Setup Coinbase Commerce
/business.payment.setup coinbase

# Create product
/business.product.create course "Blockchain Development" 99.99

# Result: Product accepting BTC, ETH, USDC, DAI
```

### Example 3: SaaS with Automatic Tax Compliance
```bash
# Setup Paddle (handles all taxes)
/business.payment.setup paddle

# Create subscription product
/business.product.create saas "Project Management Tool" 29.99

# Result: Global SaaS with automatic tax handling
```

---

## 🔧 Configuration

### Environment Variables

```bash
# PayPal
export PAYPAL_API_KEY="your_paypal_key"
export PAYPAL_API_SECRET="your_paypal_secret"

# Square
export SQUARE_API_KEY="your_square_key"
export SQUARE_API_SECRET="your_square_secret"

# Coinbase Commerce
export COINBASE_API_KEY="your_coinbase_key"

# Paddle
export PADDLE_API_KEY="your_paddle_key"
export PADDLE_API_SECRET="your_paddle_secret"

# Lemon Squeezy
export LEMONSQUEEZY_API_KEY="your_lemonsqueezy_key"
```

### Python Code

```python
from business_integrations import PaymentProcessor

# Initialize with specific provider
processor = PaymentProcessor(provider='paypal')

# Or let it use environment variables
processor = PaymentProcessor(provider='square')

# Create payment link
result = processor.create_payment_link(
    product_name="My Product",
    price=29.99,
    description="Product description",
    currency="USD"
)

print(result['payment_link'])
```

---

## 🌍 Global Considerations

### Currency Support
- **PayPal**: 25+ currencies
- **Square**: USD, CAD, GBP, EUR, AUD, JPY
- **Coinbase**: Crypto (no currency conversion needed)
- **Paddle**: 100+ currencies, automatic conversion
- **Lemon Squeezy**: 135+ currencies

### Tax Compliance
- **PayPal/Square**: You handle taxes
- **Coinbase**: Crypto (varies by jurisdiction)
- **Paddle**: Automatic global tax handling ✅
- **Lemon Squeezy**: Automatic EU VAT handling ✅

---

## 💡 Pro Tips

1. **Start with PayPal** - Most trusted, easiest to set up
2. **Add Coinbase** for crypto-savvy customers (1% fees!)
3. **Use Paddle/Lemon Squeezy** if selling globally (automatic taxes)
4. **Combine providers** - Offer multiple payment options
5. **Test in demo mode** first before going live

---

## 🎉 Why NO STRIPE?

We chose these alternatives because:

1. ✅ **Lower fees** - Coinbase at 1% vs Stripe's 2.9%
2. ✅ **Better features** - Paddle/Lemon Squeezy handle taxes
3. ✅ **More options** - Crypto, merchant of record, etc.
4. ✅ **User preference** - You explicitly didn't want Stripe
5. ✅ **Flexibility** - 5 providers vs 1

---

## 📞 Support

### List Available Providers
```bash
/business.payment.providers
```

### Check Current Setup
```bash
/business.products
```

### Switch Providers
```bash
/business.payment.setup <new_provider>
```

---

*Murphy Autonomous Business System v2.0*
*Payment Processing Without Stripe - Better Alternatives!*