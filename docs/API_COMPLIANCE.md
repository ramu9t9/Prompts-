# 🔒 Angel One API Compliance Guidelines

## ⚠️ CRITICAL: Always Follow Official API Documentation

This project uses Angel One SmartAPI and **MUST** comply with all official API guidelines, rate limits, and terms of service.

## 📚 Official Documentation Links

### Primary Resources
- **Main Documentation**: https://smartapi.angelone.in/docs
- **API Rate Limits**: https://smartapi.angelone.in/docs/rate-limits
- **SmartAPI Python SDK**: https://smartapi.angelone.in/docs/python
- **Authentication Guide**: https://smartapi.angelone.in/docs/authentication

### Additional Resources
- **Terms of Service**: https://smartapi.angelone.in/terms
- **Privacy Policy**: https://smartapi.angelone.in/privacy
- **Support**: https://smartapi.angelone.in/support

## 🔒 API Compliance Requirements

### 1. Rate Limits
- **Respect API call frequency limits**
- **Current implementation**: 3-minute intervals (within limits)
- **Monitor API response headers for rate limit info**
- **Implement exponential backoff on rate limit errors**

### 2. Authentication & Session Management
- **Use TOTP for secure authentication**
- **Handle session expiry gracefully**
- **Implement automatic re-authentication**
- **Store credentials securely (never in code)**

### 3. Error Handling
- **Implement proper error handling for all API calls**
- **Log errors for debugging**
- **Retry logic with exponential backoff**
- **Graceful degradation on API failures**

### 4. Data Usage
- **Use data only for authorized purposes**
- **Respect data retention policies**
- **Implement proper data security measures**
- **Follow Angel One's data usage terms**

### 5. Terms of Service Compliance
- **Read and follow Angel One's ToS**
- **Use API for legitimate trading purposes only**
- **Respect intellectual property rights**
- **Report any security issues**

## 📊 Current Implementation Compliance

### ✅ Implemented Features
- **Rate Limiting**: 3-minute intervals during market hours
- **Session Management**: TOTP authentication with auto-renewal
- **Error Handling**: Comprehensive error handling and logging
- **Market Hours**: Restricted to 9:18 AM - 3:30 PM IST
- **Security**: Credentials stored in environment variables/config files

### 🔄 Continuous Monitoring
- **API Response Monitoring**: Track API response times and errors
- **Rate Limit Tracking**: Monitor for rate limit violations
- **Session Health**: Check session validity before API calls
- **Data Quality**: Validate received data integrity

## 🚨 Important Warnings

### ⚠️ Never:
- **Exceed API rate limits**
- **Share API credentials**
- **Use API for unauthorized purposes**
- **Ignore API error responses**
- **Store credentials in version control**

### ✅ Always:
- **Check official documentation first**
- **Test in development environment**
- **Monitor API usage and errors**
- **Keep dependencies updated**
- **Follow security best practices**

## 🔧 Implementation Guidelines

### Code Standards
```python
# Always include API documentation reference
"""
This module uses Angel One SmartAPI.
Documentation: https://smartapi.angelone.in/docs
Rate Limits: https://smartapi.angelone.in/docs/rate-limits
"""

# Implement proper error handling
try:
    response = smart_api.getOptionChain("NFO", "NIFTY", expiry)
    if response['status']:
        # Process data
    else:
        # Handle API error
        log_error(f"API Error: {response.get('message', 'Unknown error')}")
except Exception as e:
    # Handle unexpected errors
    log_error(f"Unexpected error: {e}")
```

### Rate Limiting Implementation
```python
# Current implementation: 3-minute intervals
scheduler.add_job(
    func=fetch_and_store_all,
    trigger=CronTrigger(minute='*/3', hour='9-15'),
    id='option_chain_fetch',
    name='Fetch option chain data every 3 minutes'
)
```

## 📞 Support & Reporting

### For API Issues:
1. **Check official documentation first**
2. **Review rate limits and error codes**
3. **Contact Angel One support if needed**
4. **Report security issues immediately**

### For This Project:
1. **Check troubleshooting section in README**
2. **Review error logs**
3. **Verify credentials and permissions**
4. **Ensure market hours compliance**

---

**⚠️ Disclaimer**: This project is for educational and research purposes. Always verify data accuracy and consult financial advisors before making trading decisions. Follow all Angel One API guidelines and terms of service. 