"""
AWS Integration — Murphy System World Model Connector.

Thin wrapper around boto3 for S3, Lambda, SES, SNS, SQS.
Required credentials: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
Setup: https://console.aws.amazon.com/iam/
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .base_connector import BaseIntegrationConnector


class AWSConnector(BaseIntegrationConnector):
    """AWS SDK connector (boto3 wrapper)."""

    INTEGRATION_NAME = "AWS"
    BASE_URL = ""  # AWS uses boto3, not HTTP directly
    CREDENTIAL_KEYS = [
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
        "AWS_DEFAULT_REGION", "AWS_SESSION_TOKEN",
    ]
    REQUIRED_CREDENTIALS = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
    FREE_TIER = True
    SETUP_URL = "https://console.aws.amazon.com/iam/home#/security_credentials"
    DOCUMENTATION_URL = "https://docs.aws.amazon.com/pythonsdk/"

    def __init__(self, credentials=None, **kwargs):
        super().__init__(credentials=credentials, **kwargs)
        self._session: Any = None

    def _get_session(self) -> Any:
        """Lazily create a boto3 session."""
        if self._session is not None:
            return self._session
        try:
            import boto3  # type: ignore[import-untyped]
            self._session = boto3.Session(
                aws_access_key_id=self._credentials.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=self._credentials.get("AWS_SECRET_ACCESS_KEY"),
                aws_session_token=self._credentials.get("AWS_SESSION_TOKEN"),
                region_name=self._credentials.get("AWS_DEFAULT_REGION", "us-east-1"),
            )
            return self._session
        except ImportError:
            return None

    def _client(self, service: str) -> Any:
        session = self._get_session()
        if session is None:
            return None
        return session.client(service)

    def _wrap(self, fn) -> Dict[str, Any]:
        try:
            result = fn()
            return {"success": True, "data": result, "configured": True}
        except Exception as exc:
            return {"success": False, "error": str(exc), "configured": True}

    # -- S3 --

    def list_buckets(self) -> Dict[str, Any]:
        s3 = self._client("s3")
        if not s3:
            return {"success": False, "error": "boto3 not installed"}
        return self._wrap(s3.list_buckets)

    def list_objects(self, bucket: str, prefix: str = "",
                     max_keys: int = 100) -> Dict[str, Any]:
        s3 = self._client("s3")
        if not s3:
            return {"success": False, "error": "boto3 not installed"}
        return self._wrap(lambda: s3.list_objects_v2(Bucket=bucket, Prefix=prefix,
                                                      MaxKeys=min(max_keys, 1000)))

    def upload_file(self, bucket: str, key: str, body: bytes,
                    content_type: str = "application/octet-stream") -> Dict[str, Any]:
        s3 = self._client("s3")
        if not s3:
            return {"success": False, "error": "boto3 not installed"}
        return self._wrap(lambda: s3.put_object(Bucket=bucket, Key=key,
                                                Body=body, ContentType=content_type))

    def get_file(self, bucket: str, key: str) -> Dict[str, Any]:
        s3 = self._client("s3")
        if not s3:
            return {"success": False, "error": "boto3 not installed"}
        return self._wrap(lambda: s3.get_object(Bucket=bucket, Key=key))

    def delete_file(self, bucket: str, key: str) -> Dict[str, Any]:
        s3 = self._client("s3")
        if not s3:
            return {"success": False, "error": "boto3 not installed"}
        return self._wrap(lambda: s3.delete_object(Bucket=bucket, Key=key))

    # -- SES (Email) --

    def send_email(self, to: str, from_: str, subject: str,
                   html_body: str, text_body: str = "") -> Dict[str, Any]:
        ses = self._client("ses")
        if not ses:
            return {"success": False, "error": "boto3 not installed"}
        body: Dict[str, Any] = {"Html": {"Data": html_body, "Charset": "UTF-8"}}
        if text_body:
            body["Text"] = {"Data": text_body, "Charset": "UTF-8"}
        return self._wrap(lambda: ses.send_email(
            Source=from_,
            Destination={"ToAddresses": [to]},
            Message={"Subject": {"Data": subject, "Charset": "UTF-8"}, "Body": body},
        ))

    # -- SNS (Notifications) --

    def list_topics(self) -> Dict[str, Any]:
        sns = self._client("sns")
        if not sns:
            return {"success": False, "error": "boto3 not installed"}
        return self._wrap(sns.list_topics)

    def publish_message(self, topic_arn: str, message: str,
                        subject: str = "") -> Dict[str, Any]:
        sns = self._client("sns")
        if not sns:
            return {"success": False, "error": "boto3 not installed"}
        kwargs: Dict[str, Any] = {"TopicArn": topic_arn, "Message": message}
        if subject:
            kwargs["Subject"] = subject
        return self._wrap(lambda: sns.publish(**kwargs))

    # -- SQS --

    def list_queues(self) -> Dict[str, Any]:
        sqs = self._client("sqs")
        if not sqs:
            return {"success": False, "error": "boto3 not installed"}
        return self._wrap(sqs.list_queues)

    def send_message(self, queue_url: str, message_body: str,
                     delay_seconds: int = 0) -> Dict[str, Any]:
        sqs = self._client("sqs")
        if not sqs:
            return {"success": False, "error": "boto3 not installed"}
        return self._wrap(lambda: sqs.send_message(
            QueueUrl=queue_url, MessageBody=message_body,
            DelaySeconds=delay_seconds,
        ))

    def receive_messages(self, queue_url: str,
                         max_number: int = 10,
                         wait_time_seconds: int = 0) -> Dict[str, Any]:
        sqs = self._client("sqs")
        if not sqs:
            return {"success": False, "error": "boto3 not installed"}
        return self._wrap(lambda: sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=min(max_number, 10),
            WaitTimeSeconds=wait_time_seconds,
        ))

    # -- Lambda --

    def list_functions(self) -> Dict[str, Any]:
        lm = self._client("lambda")
        if not lm:
            return {"success": False, "error": "boto3 not installed"}
        return self._wrap(lm.list_functions)

    def invoke_function(self, function_name: str,
                        payload: Optional[Dict[str, Any]] = None,
                        invocation_type: str = "RequestResponse") -> Dict[str, Any]:
        lm = self._client("lambda")
        if not lm:
            return {"success": False, "error": "boto3 not installed"}
        import json
        return self._wrap(lambda: lm.invoke(
            FunctionName=function_name,
            InvocationType=invocation_type,
            Payload=json.dumps(payload or {}).encode(),
        ))

    # -- No-op HTTP methods (boto3 connector doesn't use HTTP directly) --
    def _get(self, *args, **kwargs) -> Dict[str, Any]:  # type: ignore[override]
        return {"success": False, "error": "AWS connector uses boto3, not HTTP"}

    def _post(self, *args, **kwargs) -> Dict[str, Any]:  # type: ignore[override]
        return {"success": False, "error": "AWS connector uses boto3, not HTTP"}
