from .models import LeakRecord

def enrich_with_osint(record: LeakRecord) -> LeakRecord:
    """
    osint를 통해 빈 LeakRecord 필드 채우는 함수
    """

    if record.author==None:
        pass

    if record.posted_at==None:
        pass

    if record.leak_types==[]:
        pass

    if record.estimated_volume==None:
        pass

    if record.file_formats==[]:
        pass

    if record.target_service==None:
        pass

    if record.domains==[]:
        pass

    if record.country==None:
        pass

    if record.threat_claim==None:
        pass

    if record.deal_terms==None:
        pass

    if record.screenshot_refs==[]:
        pass

    return record