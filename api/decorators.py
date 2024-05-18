
def check_valid_token(func):
    def wrapper(*args, **kwargs):
        company = None
        if 'company' in kwargs:
            company = kwargs['company']
        elif 'woffu_user' in kwargs:
            company = kwargs['woffu_user'].company
        if company and not company.is_valid_token():
            # Check if the token is not valid
            company.get_company_token(company=company)
        return func(*args, **kwargs)
    return wrapper
