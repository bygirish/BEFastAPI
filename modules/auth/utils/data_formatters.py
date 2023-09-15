

def remove_empty_auth_gsi_key(item: dict):
    if item.get('email_id', None) is None or len(item.get('email_id', None)) == 0:
        if "email_id" in item:
            item.pop("email_id")
    if item.get('phone_number', None) is None or len(item.get('phone_number', None)) == 0:
        if "phone_number" in item:
            item.pop("phone_number")



        def remove_empty_gsi_key(item: dict):
            if item.get("email_hash", None) is None or len(item.get("email_hash", None)) == 0:
                if "email_hash" in item:
                    item.pop("email_hash")
            if item.get("mobile_number_hash", None) is None or len(
                    item.get("mobile_number_hash", None)) == 0:
                if "mobile_number_hash" in item:
                    item.pop("mobile_number_hash")
            if not item.get("original_base_lead_id", None):
                if "original_base_lead_id" in item:
                    item.pop("original_base_lead_id")
            if "practice_id" in item and not item.get("practice_id", None):
                item.pop("practice_id")