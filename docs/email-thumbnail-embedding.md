# Email Thumbnail Embedding

## Overview

The LeadFactory email system now embeds website thumbnails (screenshots) in outreach emails alongside the proposed design mockups. This provides recipients with a visual comparison between their current website and the proposed improvements.

## Architecture

### Attachment Structure

Emails now include two inline images:

1. **Website Thumbnail** (`website-thumbnail.png`)
   - Current website screenshot
   - Smaller size (300px max width)
   - Appears first in the email

2. **Website Mockup** (`website-mockup.png`)
   - Proposed design mockup
   - Full size display
   - Appears after the thumbnail

### Content-ID References

Both images are embedded using Content-ID (CID) references:

```html
<!-- Thumbnail -->
<img src="cid:website-thumbnail.png" alt="Current Website">

<!-- Mockup -->
<img src="cid:website-mockup.png" alt="Proposed Design">
```

## Implementation Details

### Email Queue Processing

The `email_queue.py` module handles attachment preparation:

1. Retrieves screenshot asset from database
2. Retrieves mockup asset from database
3. Reads both image files from disk
4. Base64 encodes the content
5. Creates inline attachments with unique Content-IDs
6. Embeds both in the email

### Graceful Degradation

- If screenshot is missing: Email sends with mockup only
- If screenshot file not found: Warning logged, email continues
- If mockup is missing: Email fails (mockup is required)

### Email Template Structure

```html
<!-- Current Website Section -->
<div style="margin: 20px 0; text-align: center;">
    <p style="color: #7f8c8d; font-size: 14px;">Current Website:</p>
    <img src="cid:website-thumbnail.png" style="max-width: 300px;">
</div>

<!-- Proposed Design Section -->
<div class="mockup-container">
    <p><strong>Here's how your website could look:</strong></p>
    <img src="cid:website-mockup.png" class="mockup">
</div>
```

## Configuration

No additional configuration required. The system automatically:

1. Checks for screenshot assets
2. Embeds if available
3. Continues without if not available

## Testing

### Unit Tests
- `test_email_thumbnail.py` - Attachment creation and encoding

### Integration Tests
- `test_email_thumbnail_integration.py` - Database integration and full flow

### BDD Tests
- `email_thumbnail.feature` - Business scenarios

## Usage

### Command Line

```bash
# Send emails with thumbnails
python -m leadfactory.pipeline.email_queue --limit 10

# Dry run to test
python -m leadfactory.pipeline.email_queue --dry-run
```

### Python API

```python
from leadfactory.pipeline.email_queue import send_business_email

# Business must have both screenshot and mockup assets
business = {
    "id": 123,
    "name": "Test Business",
    "email": "test@example.com"
}

success = send_business_email(business)
```

## Performance Considerations

- **File Size**: Screenshots are typically 100-500KB
- **Email Size**: Total email with both images: 200KB-1MB
- **Processing Time**: ~100ms per email for attachment encoding

## Best Practices

1. **Generate screenshots before mockups** in the pipeline
2. **Optimize image sizes** to reduce email size
3. **Use consistent dimensions** for better layout
4. **Monitor bounce rates** for large emails
5. **Consider email client compatibility**

## Email Client Compatibility

Tested and working in:
- Gmail (Web & Mobile)
- Outlook (2016+)
- Apple Mail
- Yahoo Mail
- Mobile clients (iOS/Android)

## Troubleshooting

### Common Issues

1. **"Failed to read screenshot file"**
   - Check file permissions
   - Verify path in assets table
   - Ensure file exists on disk

2. **Images not displaying**
   - Check Content-ID matches
   - Verify inline disposition
   - Test email client settings

3. **Email too large**
   - Optimize image compression
   - Reduce image dimensions
   - Consider linking instead of embedding

### Debug Mode

Enable debug logging:

```python
import logging
logging.getLogger('leadfactory.pipeline.email_queue').setLevel(logging.DEBUG)
```

## Future Enhancements

- [ ] A/B testing with/without thumbnails
- [ ] Dynamic thumbnail sizing based on original
- [ ] Multiple screenshot angles
- [ ] Before/after slider in email
- [ ] Lazy loading for email clients
