# Install Visual Studio Build Tools for Python 3.13

## What This Does

Installs the C++ compiler needed to build Python packages like `aiohttp` from source.

**Warning:** This is a **6+ GB download** and takes 30-60 minutes to install.

---

## Step-by-Step Instructions

### Step 1: Download Build Tools

1. Go to: https://visualstudio.microsoft.com/visual-cpp-build-tools/
2. Click: **Download Build Tools**
3. File: `vs_BuildTools.exe` (~3 MB installer, downloads 6+ GB during install)

### Step 2: Run Installer

1. Run `vs_BuildTools.exe`
2. Wait for the Visual Studio Installer to load
3. You'll see a screen with different workloads

### Step 3: Select Workload

**IMPORTANT:** Select **"Desktop development with C++"**

This includes:
- MSVC v143 - VS 2022 C++ x64/x86 build tools
- Windows 10/11 SDK
- C++ CMake tools
- Testing tools

**Make sure this workload is checked!**

### Step 4: Install

1. Click **Install** (bottom right)
2. Accept the license agreement
3. Wait for download and installation (30-60 minutes)
4. **Restart your computer** when prompted

### Step 5: Verify Installation

Open Command Prompt and run:

```bash
cl
```

Should show:
```
Microsoft (R) C/C++ Optimizing Compiler Version 19.xx.xxxxx
```

If you see this, the compiler is installed!

### Step 6: Install aiohttp

Now you can install aiohttp:

```bash
cd C:\Users\inoni\Downloads\murphy_system\murphy_system
pip install aiohttp==3.9.1
```

Should now work without errors!

### Step 7: Verify aiohttp

```bash
python -c "import aiohttp; print('SUCCESS:', aiohttp.__version__)"
```

Should show:
```
SUCCESS: 3.9.1
```

### Step 8: Start Murphy

```bash
start_murphy.bat
```

Check logs - should now see:
```
✓ Enhanced LLM Provider initialized
  - Groq keys: 9
```

No more errors!

---

## Troubleshooting

### Issue: Installer says "Visual Studio already installed"

**Solution:** You might have Visual Studio Code (different from Build Tools)

1. In the installer, click **Modify**
2. Select "Desktop development with C++"
3. Click **Modify** to install

### Issue: Still getting compiler errors after install

**Solution:** Restart computer

The PATH environment variable needs to be updated. Restart fixes this.

### Issue: "cl" command not found

**Solution:** Add to PATH manually

1. Press `Windows Key`
2. Search: "Environment Variables"
3. Click "Edit the system environment variables"
4. Click "Environment Variables"
5. Under "System variables", find "Path"
6. Click "Edit"
7. Click "New"
8. Add: `C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.xx.xxxxx\bin\Hostx64\x64`
   (Replace xx.xxxxx with your version)
9. Click OK
10. Restart Command Prompt

### Issue: Installation failed

**Solution:** Check disk space

- Need at least **10 GB free space**
- Installation is ~6-7 GB
- Temporary files need extra space

---

## What Gets Installed

**Total Size:** ~6-7 GB

**Components:**
- C++ compiler (cl.exe)
- Windows SDK
- MSBuild
- CMake
- C++ libraries
- Testing tools

**Location:**
```
C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\
```

---

## Alternative: Minimal Installation

If you want to save space, you can do a minimal install:

### Step 1: In the installer, click "Individual components"

### Step 2: Select ONLY these:
- ✅ MSVC v143 - VS 2022 C++ x64/x86 build tools (Latest)
- ✅ Windows 10 SDK (10.0.19041.0 or later)
- ✅ C++ CMake tools for Windows

This reduces the install to ~3-4 GB instead of 6-7 GB.

---

## After Installation

Once Build Tools are installed:

1. **Restart computer** (important!)
2. Open Command Prompt
3. Run: `pip install aiohttp==3.9.1`
4. Should install without errors
5. Run: `start_murphy.bat`
6. Murphy will work!

---

## Time Estimate

- **Download:** 10-30 minutes (depending on internet speed)
- **Installation:** 20-40 minutes
- **Total:** 30-70 minutes

---

## Is This Worth It?

**Pros:**
- Keep Python 3.13
- Can compile any Python package from source
- Useful for development

**Cons:**
- 6+ GB disk space
- 30-60 minute install
- Only needed for Python 3.13

**My Recommendation:**
If you're not doing C++ development, **downgrade to Python 3.12 instead**. It's faster and simpler.

But if you want to keep Python 3.13, installing Build Tools is the way to go!

---

## Summary

1. Download: https://visualstudio.microsoft.com/visual-cpp-build-tools/
2. Run installer
3. Select "Desktop development with C++"
4. Install (30-60 minutes)
5. Restart computer
6. Run: `pip install aiohttp==3.9.1`
7. Run: `start_murphy.bat`

Done!