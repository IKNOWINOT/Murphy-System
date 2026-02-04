# Murphy System - Complete Installation Guide

## 📦 What You Have

This is a **complete, fresh installation** of the Murphy AI Agent System with ALL necessary files included.

## 🎯 Installation Steps

### Step 1: Extract Files

Extract this entire folder to your desired location.

### Step 2: Verify Python Version

**IMPORTANT:** You must use Python 3.11 or 3.12 (NOT 3.13)

Check your version:
```bash
python --version
```

### Step 3: Set Up API Keys

#### Groq API Keys (Required)

1. Open `groq_keys.txt`
2. Delete the example lines
3. Add your Groq API keys, one per line:
```
gsk_your_first_key_here
gsk_your_second_key_here
gsk_your_third_key_here
```

#### Aristotle API Key (Optional)

1. Open `aristotle_key.txt`
2. Delete the example line
3. Add your Aristotle API key

### Step 4: Install Dependencies

**Windows:**
```bash
pip install -r requirements.txt
```

**Linux/Mac:**
```bash
pip3 install -r requirements.txt
```

### Step 5: Start the Server

**Windows:**
```bash
python murphy_complete_integrated.py
```

**Linux/Mac:**
```bash
python3 murphy_complete_integrated.py
```

### Step 6: Access the UI

Open your browser: http://localhost:3002

## ✅ Verify Installation

Test these commands:
```
/status
/librarian What can Murphy do?
Hello Murphy!
```

## 🔧 Troubleshooting

See README.md for troubleshooting tips.

## 🎊 Success!

You now have a complete Murphy AI Agent System ready to use!