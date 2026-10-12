"""Private Supabase Storage access for payment receipts (server-side only)."""
import os
from urllib.parse import quote

import requests


class ReceiptStorageError(Exception):
    pass


def _config():
    base = os.environ.get('SUPABASE_URL', '').rstrip('/')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    bucket = os.environ.get('SUPABASE_BUCKET', 'payment-receipts')
    if not base.startswith('https://') or not key or not bucket:
        raise ReceiptStorageError('Supabase Storage is not configured.')
    return base, key, bucket


def _url(path):
    base, _, bucket = _config()
    return f'{base}/storage/v1/object/{quote(bucket, safe="")}/{quote(path, safe="/")}'


def _headers():
    _, key, _ = _config()
    return {'apikey': key, 'Authorization': f'Bearer {key}'}


def upload_receipt(path, data, mime_type):
    try:
        response = requests.post(
            _url(path),
            headers={**_headers(), 'Content-Type': mime_type, 'x-upsert': 'false'},
            data=data,
            timeout=25,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ReceiptStorageError('Could not upload receipt to Supabase Storage.') from exc


def delete_receipt(path):
    try:
        response = requests.delete(_url(path), headers=_headers(), timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ReceiptStorageError('Could not delete receipt from Supabase Storage.') from exc


def get_receipt(path):
    try:
        response = requests.get(_url(path), headers=_headers(), timeout=20)
    except requests.RequestException as exc:
        raise ReceiptStorageError('Could not retrieve receipt from Supabase Storage.') from exc
    if response.status_code == 404:
        return None
    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ReceiptStorageError('Could not retrieve receipt from Supabase Storage.') from exc
    return response.content
