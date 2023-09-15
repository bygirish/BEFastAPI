from configs.env import app_env

__dynamodb_table_prefixes = {
    "prod": "prod",
    "dev": "dev",
    "stage": "stage",
    "local": "dev"
}


def dynamodb_table_prefix_config():
    return __dynamodb_table_prefixes[app_env()]


__env_config_prefixes = {
    "prod": "prod",
    "dev": "dev",
    "stage": "stage",
    "local": "dev"
}


def env_config_prefix_config():
    return __env_config_prefixes[app_env()]


__tld = {
    "prod": "test.com",
    "dev": "dev.test.com",
    "stage": "stage.test.com",
    "local": "local.test.com"
}


def cookie_domain_config():
    return __tld[app_env()]
