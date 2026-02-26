#!/bin/bash
# Creates the Qdrant 'deals' collection with correct dimensions and settings
# Run after docker compose up if setup.sh missed it

curl -X PUT http://localhost:6333/collections/deals \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 1536,
      "distance": "Cosine",
      "on_disk": false
    },
    "optimizers_config": {
      "default_segment_number": 2
    },
    "quantization_config": {
      "scalar": {
        "type": "int8",
        "quantile": 0.99,
        "always_ram": true
      }
    }
  }' && echo "" && echo "✓ Qdrant 'deals' collection ready"
