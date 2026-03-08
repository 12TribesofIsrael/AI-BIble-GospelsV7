# 📝 Changelog - v6.0.1

**Release Date**: February 18, 2026  
**Type**: Hotfix  
**Status**: Superseded by v6.0.2

---

## 🐛 Bug Fixes

### **Fixed: Perplexity AI JSON Parsing Failure**
**Issue**: Workflow failing with error `No JSON object found in response`

**Root Cause**: Perplexity AI's `sonar-pro` model sometimes wraps JSON responses in markdown code blocks (` ```json ... ``` `), which the original regex pattern failed to extract.

**Solution**: Implemented 3-level fallback strategy for JSON extraction:
1. Extract from markdown code blocks (` ```json...``` `)
2. Find JSON object with regex match
3. Parse entire response as-is

**Code Changes**:
- Enhanced `jsCode` in "Enhanced Format for 16:9 Template" node
- Added markdown code block detection
- Improved error messages with response preview (first 500 chars)
- Updated version string to `Template Variables v6.3 - Enhanced JSON Parsing`

**Impact**: Workflow can now handle all Perplexity response formats without parsing errors.

---

## 📦 Files in This Release

- `Biblical-Video-Workflow-v6.0.1.json` - Updated workflow with JSON parsing fix

---

## ⚠️ Known Issues

- **JSON2Video 500 Errors**: Scenes may fail with "Request failed with status code 500" due to missing `zoomEnd` and `panEnd` template variables
- **Affected Scenes**: Typically scenes #1, #11, #13 (zoom-in and ken-burns motion types)
- **Fix**: Upgrade to v6.0.2

---

## 🔄 Migration from v6.0.0

Simply replace your workflow with this version. No configuration changes needed.

**Breaking Changes**: None

---

## 📚 Documentation

- `RELEASE_NOTES_v6.0.1.md` - Complete fix documentation with examples

---

**Next Version**: v6.0.2 (JSON2Video 500 error fix)
