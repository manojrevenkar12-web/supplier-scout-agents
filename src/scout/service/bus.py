"""Search requests travel over Pub/Sub: the API publishes, workers pull. An in-memory bus for tests and local runs."""

from __future__ import annotations

import json
from collections import deque
from typing import Protocol


class Bus(Protocol):
    def publish(self, topic: str, message: dict) -> str: ...
    def pull(self, subscription: str, max_messages: int) -> list[tuple[str, dict]]: ...
    def ack(self, subscription: str, ack_ids: list[str]) -> None: ...


class MemoryBus:
    def __init__(self) -> None:
        self.queues: dict[str, deque] = {}
        self.unacked: dict[str, dict] = {}
        self.n = 0

    def publish(self, topic: str, message: dict) -> str:
        self.n += 1
        mid = f"m{self.n}"
        self.queues.setdefault(topic, deque()).append((mid, json.loads(json.dumps(message))))
        return mid

    def pull(self, subscription: str, max_messages: int) -> list[tuple[str, dict]]:
        q = self.queues.get(subscription, deque())
        out = [q.popleft() for _ in range(min(max_messages, len(q)))]
        self.unacked.update({mid: (subscription, m) for mid, m in out})
        return out

    def ack(self, subscription: str, ack_ids: list[str]) -> None:
        for a in ack_ids:
            self.unacked.pop(a, None)

    def redeliver(self) -> None:
        """What Pub/Sub does when an ack deadline passes: unacked messages come back."""
        for mid, (sub, m) in list(self.unacked.items()):
            self.queues.setdefault(sub, deque()).appendleft((mid, m))
        self.unacked.clear()


class GcpPubSub:
    """google-cloud-pubsub (pip install '.[gcp]'); topic and subscription names map 1:1 to the Terraform."""

    def __init__(self, project: str):
        from google.cloud import pubsub_v1  # noqa: PLC0415

        self.project = project
        self.pub = pubsub_v1.PublisherClient()
        self.sub = pubsub_v1.SubscriberClient()

    def publish(self, topic: str, message: dict) -> str:
        return self.pub.publish(self.pub.topic_path(self.project, topic), json.dumps(message).encode()).result()

    def pull(self, subscription: str, max_messages: int) -> list[tuple[str, dict]]:
        path = self.sub.subscription_path(self.project, subscription)
        resp = self.sub.pull(request={"subscription": path, "max_messages": max_messages})
        return [(m.ack_id, json.loads(m.message.data)) for m in resp.received_messages]

    def ack(self, subscription: str, ack_ids: list[str]) -> None:
        if ack_ids:
            self.sub.acknowledge(
                request={"subscription": self.sub.subscription_path(self.project, subscription), "ack_ids": ack_ids}
            )
