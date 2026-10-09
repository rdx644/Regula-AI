"""Actual boto3 HTTP transport to an isolated local S3 emulator; no cloud access."""
from uuid import uuid4
import pytest
import boto3
from moto.server import ThreadedMotoServer
from app.core.config import settings
from app.services.storage import PrivateS3Storage


@pytest.fixture
def s3(monkeypatch):
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'synthetic-test-only')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'synthetic-test-only')
    monkeypatch.setenv('AWS_EC2_METADATA_DISABLED', 'true')
    server = ThreadedMotoServer(ip_address='127.0.0.1', port=0, verbose=False)
    server.start()
    host, port = server.get_host_and_port()
    endpoint = f'http://{host}:{port}'
    bucket = 'regulaai-' + uuid4().hex
    client = boto3.client('s3', region_name='us-east-1', endpoint_url=endpoint)
    client.create_bucket(Bucket=bucket)
    client.put_public_access_block(Bucket=bucket, PublicAccessBlockConfiguration={key: True for key in ['BlockPublicAcls', 'IgnorePublicAcls', 'BlockPublicPolicy', 'RestrictPublicBuckets']})
    client.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={'Status': 'Enabled'})
    client.put_bucket_encryption(Bucket=bucket, ServerSideEncryptionConfiguration={'Rules': [{'ApplyServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'}}]})
    monkeypatch.setattr(settings, 'S3_BUCKET', bucket)
    monkeypatch.setattr(settings, 'S3_ENDPOINT_URL', endpoint)
    monkeypatch.setattr(settings, 'AWS_REGION', 'us-east-1')
    try:
        yield PrivateS3Storage(), client, bucket
    finally:
        server.stop()


def test_private_encrypted_versioned_storage_and_object_restore(s3):
    storage, client, bucket = s3
    assert storage.verify_configuration()
    org, resource = uuid4(), uuid4()
    key = storage.save(org, resource, '.txt', b'Synthetic private source')
    assert key.startswith(f'regulations/{org}/{resource}/')
    assert storage.read(key) == b'Synthetic private source'
    original = client.head_object(Bucket=bucket, Key=key)
    assert original['ServerSideEncryption'] == 'AES256'
    assert client.get_object_acl(Bucket=bucket, Key=key)['Grants'][0]['Permission'] == 'FULL_CONTROL'
    storage.delete(key)
    client.copy_object(Bucket=bucket, Key=key, CopySource={'Bucket': bucket, 'Key': key, 'VersionId': original['VersionId']}, ServerSideEncryption='AES256')
    assert storage.read(key) == b'Synthetic private source'


def test_unsafe_bucket_is_rejected(s3):
    storage, client, bucket = s3
    client.put_public_access_block(Bucket=bucket, PublicAccessBlockConfiguration={'BlockPublicAcls': False, 'IgnorePublicAcls': False, 'BlockPublicPolicy': False, 'RestrictPublicBuckets': False})
    with pytest.raises(RuntimeError, match='public access'):
        storage.verify_configuration()
