# 📝 Changelog - v6.0.2

**Release Date**: February 18, 2026  
**Type**: Hotfix  
**Status**: ✅ CURRENT STABLE

---

## 🐛 Bug Fixes

### **Fixed: JSON2Video 500 Internal Server Errors**
**Issue**: Video generation failing with errors on scenes #1, #11, #13:
```
Scene #1, element #1: Request failed with status code 500
Scene #11, element #1: Request failed with status code 500
Scene #13, element #1: Request failed with status code 500
```

**Root Cause**: Workflow sending incomplete Ken Burns animation variables to JSON2Video API:
- ✅ Sent: `zoomStart`, `panStart`
- ❌ Missing: `zoomEnd`, `panEnd`
- Result: JSON2Video received literal template strings like `"{{scene1_zoomEnd}}"` instead of numeric values

**Solution**: Added missing `zoomEnd` and `panEnd` variables for all 5 motion types:

| Motion Type | zoomStart | zoomEnd (NEW) | panStart | panEnd (NEW) |
|-------------|-----------|---------------|----------|--------------|
| zoom-in | 2 | **0** ✅ | center | **center** ✅ |
| zoom-out | -2 | **0** ✅ | center | **center** ✅ |
| ken-burns | 1 | **0** ✅ | left | **right** ✅ |
| pan-right | 0 | **0** ✅ | left | **right** ✅ |
| pan-left | 0 | **0** ✅ | right | **left** ✅ |

**Code Changes**:
- Updated `jsCode` in "Enhanced Format for 16:9 Template" node
- Added `zoomEnd` and `panEnd` for every scene (40 new variables total)
- Updated version string to `Template Variables v6.4 - Fixed Missing zoomEnd/panEnd`

**Impact**: All 20 scenes now render successfully without 500 errors.

---

## ✨ Includes All Fixes From v6.0.1

- ✅ Enhanced JSON parsing (markdown code block support)
- ✅ Complete Ken Burns animation variables

---

## 📦 Files in This Release

- `Biblical-Video-Workflow-v6.0.2.json` - Fully fixed workflow (all issues resolved)
- `RELEASE_NOTES_v6.0.2.md` - Complete fix documentation
- `CHANGELOG_v6.0.2.md` - This file

---

## ⚠️ Known Issues

None currently reported. All critical issues resolved.

---

## 🔄 Migration from Previous Versions

### From v6.0.0 or v6.0.1:
1. Export your current workflow (backup)
2. Import `Biblical-Video-Workflow-v6.0.2.json`
3. Re-configure API credentials (Perplexity, ElevenLabs, JSON2Video)
4. Test with sample biblical text

**Breaking Changes**: None

---

## 📊 Version Comparison

| Feature | v6.0.0 | v6.0.1 | v6.0.2 |
|---------|--------|--------|--------|
| Perplexity JSON Parsing | ❌ Basic | ✅ Enhanced | ✅ Enhanced |
| Markdown Code Blocks | ❌ No | ✅ Yes | ✅ Yes |
| zoomEnd Variables | ❌ Missing | ❌ Missing | ✅ Complete |
| panEnd Variables | ❌ Missing | ❌ Missing | ✅ Complete |
| JSON2Video 500 Errors | ❌ Yes | ❌ Yes | ✅ Fixed |
| Production Ready | ⚠️ Partial | ⚠️ Partial | ✅ Yes |

---

## 📚 Documentation

- `RELEASE_NOTES_v6.0.2.md` - Complete fix documentation with troubleshooting
- `CHANGELOG_v6.0.2.md` - This changelog

---

## 🎯 Recommendation

**Use v6.0.2 for all new projects**. This version includes all fixes and is fully production-ready.

---

**Previous Version**: v6.0.1  
**Next Version**: TBD
