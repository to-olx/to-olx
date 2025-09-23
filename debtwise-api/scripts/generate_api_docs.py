#!/usr/bin/env python3
"""
Generate API documentation in various formats.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app
from app.core.openapi import custom_openapi


async def generate_openapi_json():
    """Generate OpenAPI JSON specification."""
    schema = custom_openapi(app)
    
    # Create docs directory
    docs_dir = Path("docs/api")
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    # Write OpenAPI JSON
    openapi_path = docs_dir / "openapi.json"
    with open(openapi_path, "w") as f:
        json.dump(schema, f, indent=2)
    
    print(f"✅ Generated OpenAPI JSON: {openapi_path}")
    return schema


async def generate_markdown_docs(schema: dict):
    """Generate Markdown documentation from OpenAPI schema."""
    docs_dir = Path("docs/api")
    
    # Generate main API documentation
    md_content = [
        "# DebtWise API Documentation\n",
        f"**Version:** {schema['info']['version']}\n",
        f"**Base URL:** {schema['servers'][0]['url']}\n",
        "\n## Description\n",
        schema["info"]["description"],
        "\n## Authentication\n",
        "This API uses JWT Bearer tokens for authentication. Include the token in the Authorization header:\n",
        "```\nAuthorization: Bearer <your-token>\n```\n",
        "\n## Endpoints\n",
    ]
    
    # Group endpoints by tags
    endpoints_by_tag = {}
    for path, methods in schema["paths"].items():
        for method, details in methods.items():
            if method in ["get", "post", "put", "patch", "delete"]:
                tags = details.get("tags", ["Other"])
                for tag in tags:
                    if tag not in endpoints_by_tag:
                        endpoints_by_tag[tag] = []
                    endpoints_by_tag[tag].append({
                        "path": path,
                        "method": method.upper(),
                        "summary": details.get("summary", ""),
                        "description": details.get("description", ""),
                        "operationId": details.get("operationId", ""),
                    })
    
    # Write endpoints by tag
    for tag, endpoints in endpoints_by_tag.items():
        md_content.append(f"\n### {tag}\n")
        
        for endpoint in endpoints:
            md_content.append(f"\n#### {endpoint['method']} `{endpoint['path']}`\n")
            if endpoint['summary']:
                md_content.append(f"**{endpoint['summary']}**\n")
            if endpoint['description']:
                md_content.append(f"\n{endpoint['description']}\n")
    
    # Write to file
    md_path = docs_dir / "API_REFERENCE.md"
    with open(md_path, "w") as f:
        f.writelines(md_content)
    
    print(f"✅ Generated Markdown docs: {md_path}")


async def generate_postman_collection(schema: dict):
    """Generate Postman collection from OpenAPI schema."""
    docs_dir = Path("docs/api")
    
    collection = {
        "info": {
            "name": "DebtWise API",
            "description": "DebtWise API Postman Collection",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "item": [],
        "variable": [
            {
                "key": "base_url",
                "value": schema["servers"][0]["url"],
                "type": "string"
            },
            {
                "key": "access_token",
                "value": "",
                "type": "string"
            }
        ],
        "auth": {
            "type": "bearer",
            "bearer": [
                {
                    "key": "token",
                    "value": "{{access_token}}",
                    "type": "string"
                }
            ]
        }
    }
    
    # Group by tags
    folders = {}
    
    for path, methods in schema["paths"].items():
        for method, details in methods.items():
            if method in ["get", "post", "put", "patch", "delete"]:
                tags = details.get("tags", ["Other"])
                tag = tags[0]
                
                if tag not in folders:
                    folders[tag] = {
                        "name": tag,
                        "item": []
                    }
                
                # Create request item
                request_item = {
                    "name": details.get("summary", f"{method.upper()} {path}"),
                    "request": {
                        "method": method.upper(),
                        "header": [],
                        "url": {
                            "raw": "{{base_url}}" + path,
                            "host": ["{{base_url}}"],
                            "path": path.strip("/").split("/")
                        }
                    }
                }
                
                # Add request body if needed
                if "requestBody" in details:
                    content = details["requestBody"].get("content", {})
                    if "application/json" in content:
                        example = content["application/json"].get("example", {})
                        request_item["request"]["body"] = {
                            "mode": "raw",
                            "raw": json.dumps(example, indent=2),
                            "options": {
                                "raw": {
                                    "language": "json"
                                }
                            }
                        }
                        request_item["request"]["header"].append({
                            "key": "Content-Type",
                            "value": "application/json"
                        })
                
                folders[tag]["item"].append(request_item)
    
    collection["item"] = list(folders.values())
    
    # Write collection
    postman_path = docs_dir / "DebtWise_API.postman_collection.json"
    with open(postman_path, "w") as f:
        json.dump(collection, f, indent=2)
    
    print(f"✅ Generated Postman collection: {postman_path}")


async def generate_api_client_examples():
    """Generate API client examples in various languages."""
    docs_dir = Path("docs/api/examples")
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    # Python example
    python_example = '''"""
DebtWise API Python Client Example
"""

import requests
from datetime import datetime


class DebtWiseClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.token = None
        
    def register(self, email, password, full_name):
        """Register a new user."""
        response = requests.post(
            f"{self.base_url}/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "full_name": full_name
            }
        )
        return response.json()
    
    def login(self, email, password):
        """Login and store access token."""
        response = requests.post(
            f"{self.base_url}/api/v1/auth/login",
            data={
                "username": email,
                "password": password
            }
        )
        if response.status_code == 200:
            data = response.json()
            self.token = data["access_token"]
        return response.json()
    
    def create_transaction(self, amount, category, description, date=None):
        """Create a new transaction."""
        if not self.token:
            raise Exception("Not authenticated. Please login first.")
        
        response = requests.post(
            f"{self.base_url}/api/v1/transactions",
            headers={
                "Authorization": f"Bearer {self.token}"
            },
            json={
                "amount": amount,
                "category": category,
                "description": description,
                "date": date or datetime.now().date().isoformat(),
                "type": "expense" if amount < 0 else "income"
            }
        )
        return response.json()
    
    def get_transactions(self, limit=10):
        """Get user transactions."""
        if not self.token:
            raise Exception("Not authenticated. Please login first.")
        
        response = requests.get(
            f"{self.base_url}/api/v1/transactions",
            headers={
                "Authorization": f"Bearer {self.token}"
            },
            params={"limit": limit}
        )
        return response.json()


# Example usage
if __name__ == "__main__":
    client = DebtWiseClient()
    
    # Register
    # client.register("user@example.com", "SecurePassword123!", "John Doe")
    
    # Login
    client.login("user@example.com", "SecurePassword123!")
    
    # Create transaction
    client.create_transaction(
        amount=-45.99,
        category="Food",
        description="Grocery shopping"
    )
    
    # Get transactions
    transactions = client.get_transactions()
    print(transactions)
'''
    
    # JavaScript example
    javascript_example = '''/**
 * DebtWise API JavaScript Client Example
 */

class DebtWiseClient {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
        this.token = null;
    }
    
    async register(email, password, fullName) {
        const response = await fetch(`${this.baseUrl}/api/v1/auth/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                email,
                password,
                full_name: fullName,
            }),
        });
        return response.json();
    }
    
    async login(email, password) {
        const formData = new FormData();
        formData.append('username', email);
        formData.append('password', password);
        
        const response = await fetch(`${this.baseUrl}/api/v1/auth/login`, {
            method: 'POST',
            body: formData,
        });
        
        if (response.ok) {
            const data = await response.json();
            this.token = data.access_token;
        }
        return response.json();
    }
    
    async createTransaction(amount, category, description, date = null) {
        if (!this.token) {
            throw new Error('Not authenticated. Please login first.');
        }
        
        const response = await fetch(`${this.baseUrl}/api/v1/transactions`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.token}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                amount,
                category,
                description,
                date: date || new Date().toISOString().split('T')[0],
                type: amount < 0 ? 'expense' : 'income',
            }),
        });
        return response.json();
    }
    
    async getTransactions(limit = 10) {
        if (!this.token) {
            throw new Error('Not authenticated. Please login first.');
        }
        
        const response = await fetch(
            `${this.baseUrl}/api/v1/transactions?limit=${limit}`,
            {
                headers: {
                    'Authorization': `Bearer ${this.token}`,
                },
            }
        );
        return response.json();
    }
}

// Example usage
async function example() {
    const client = new DebtWiseClient();
    
    try {
        // Login
        await client.login('user@example.com', 'SecurePassword123!');
        
        // Create transaction
        await client.createTransaction(
            -45.99,
            'Food',
            'Grocery shopping'
        );
        
        // Get transactions
        const transactions = await client.getTransactions();
        console.log(transactions);
    } catch (error) {
        console.error('Error:', error);
    }
}

// Run example
example();
'''
    
    # CURL examples
    curl_example = '''#!/bin/bash
# DebtWise API cURL Examples

# Set variables
BASE_URL="http://localhost:8000"
EMAIL="user@example.com"
PASSWORD="SecurePassword123!"

# 1. Register a new user
echo "=== Registering new user ==="
curl -X POST "$BASE_URL/api/v1/auth/register" \\
  -H "Content-Type: application/json" \\
  -d '{
    "email": "'$EMAIL'",
    "password": "'$PASSWORD'",
    "full_name": "John Doe"
  }'

# 2. Login to get access token
echo -e "\\n\\n=== Logging in ==="
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \\
  -H "Content-Type: application/x-www-form-urlencoded" \\
  -d "username=$EMAIL&password=$PASSWORD")

ACCESS_TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')
echo "Access token: $ACCESS_TOKEN"

# 3. Create a transaction
echo -e "\\n\\n=== Creating transaction ==="
curl -X POST "$BASE_URL/api/v1/transactions" \\
  -H "Authorization: Bearer $ACCESS_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "amount": -45.99,
    "category": "Food",
    "description": "Grocery shopping",
    "date": "'$(date +%Y-%m-%d)'",
    "type": "expense"
  }'

# 4. Get transactions
echo -e "\\n\\n=== Getting transactions ==="
curl -X GET "$BASE_URL/api/v1/transactions?limit=10" \\
  -H "Authorization: Bearer $ACCESS_TOKEN"

# 5. Get spending analytics
echo -e "\\n\\n=== Getting spending analytics ==="
curl -X GET "$BASE_URL/api/v1/analytics/spending-summary?period=monthly" \\
  -H "Authorization: Bearer $ACCESS_TOKEN"
'''
    
    # Write examples
    with open(docs_dir / "python_example.py", "w") as f:
        f.write(python_example)
    
    with open(docs_dir / "javascript_example.js", "w") as f:
        f.write(javascript_example)
    
    with open(docs_dir / "curl_examples.sh", "w") as f:
        f.write(curl_example)
    
    os.chmod(docs_dir / "curl_examples.sh", 0o755)
    
    print(f"✅ Generated API client examples in: {docs_dir}")


async def main():
    """Generate all API documentation."""
    print("🚀 Generating DebtWise API Documentation...\n")
    
    # Generate OpenAPI JSON
    schema = await generate_openapi_json()
    
    # Generate Markdown docs
    await generate_markdown_docs(schema)
    
    # Generate Postman collection
    await generate_postman_collection(schema)
    
    # Generate client examples
    await generate_api_client_examples()
    
    print("\n✨ API documentation generation complete!")
    print("\nGenerated files:")
    print("  - docs/api/openapi.json")
    print("  - docs/api/API_REFERENCE.md")
    print("  - docs/api/DebtWise_API.postman_collection.json")
    print("  - docs/api/examples/python_example.py")
    print("  - docs/api/examples/javascript_example.js")
    print("  - docs/api/examples/curl_examples.sh")


if __name__ == "__main__":
    asyncio.run(main())