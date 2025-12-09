from .models import LeakRecord


def notify_new_leak(record: LeakRecord) -> None:
    """새 유출 정보가 추가될 때 콘솔에 알림을 출력."""
    print("\n🔔 [NEW LEAK DETECTED]")
    print(f"- Source        : {record.source}")
    print(f"- Title         : {record.post_title}")
    print(f"- Target Service: {record.target_service or 'N/A'}")
    print(f"- Domains       : {', '.join(record.domains) or 'N/A'}")
    print(f"- Leak Types    : {', '.join(record.leak_types)}")
    print(f"- Volume        : {record.estimated_volume or 'Unknown'}")
    print(f"- Confidence    : {record.confidence}")
    print("--------------------------------------------------")
