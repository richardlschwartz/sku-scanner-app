import os
import json
from flask import Flask, request, jsonify, send_from_directory
import anthropic

app = Flask(__name__, static_folder='public')
client = anthropic.Anthropic()

ANALYSIS_PROMPT = """You are a product/SKU scanner for retail and warehouse environments. Analyze this image and provide a structured JSON response.

Identify what is shown in the image. It could be:
1. A single product/SKU item
2. A case pack (a box/carton containing multiple units of a product)
3. A pallet (a shipping pallet containing multiple case packs)

Respond with ONLY valid JSON in this exact format:
{
  "item_type": "single_item" or "case_pack" or "pallet",
  "description": "Detailed description of what you see",
  "item_id": "The product ID, SKU, UPC, or barcode number if visible, otherwise null",
  "brand": "Brand name if visible, otherwise null",
  "estimated_sku_quantity": <number of individual SKU units you estimate are present, 1 for single items>,
  "estimated_case_packs": <number of case packs if this is a pallet, otherwise null>,
  "confidence": "high" or "medium" or "low",
  "additional_notes": "Any other relevant observations about the product, packaging, damage, labels, etc."
}

Be precise about quantities. For case packs, look for quantity indicators on labels (e.g., "QTY: 24", "12 PK"). For pallets, count visible case packs and estimate hidden ones based on the stacking pattern. If you cannot determine exact quantities, provide your best estimate and set confidence accordingly."""


@app.route('/')
def index():
    return send_from_directory('public', 'index.html')


@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('public', path)


@app.route('/api/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    image = data.get('image')
    media_type = data.get('mediaType', 'image/jpeg')

    if not image:
        return jsonify({'error': 'No image data provided'}), 400

    try:
        response = client.messages.create(
            model='claude-sonnet-4-20250514',
            max_tokens=1024,
            messages=[
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'image',
                            'source': {
                                'type': 'base64',
                                'media_type': media_type,
                                'data': image
                            }
                        },
                        {
                            'type': 'text',
                            'text': ANALYSIS_PROMPT
                        }
                    ]
                }
            ]
        )

        text = response.content[0].text
        try:
            import re
            json_match = re.search(r'\{[\s\S]*\}', text)
            analysis = json.loads(json_match.group() if json_match else text)
        except (json.JSONDecodeError, AttributeError):
            analysis = {
                'item_type': 'unknown',
                'description': text,
                'item_id': None,
                'brand': None,
                'estimated_sku_quantity': None,
                'estimated_case_packs': None,
                'confidence': 'low',
                'additional_notes': 'Could not parse structured response'
            }

        return jsonify(analysis)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 3456))
    app.run(host="0.0.0.0", port=port, debug=False)
