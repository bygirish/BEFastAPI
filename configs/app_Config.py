from configs.dev_config import DevConfig
from configs.env_config import EnvConfig
from configs.prod_config import ProdConfig


class AppConfig:
    __envConfig: EnvConfig = {}
    __buildConfig: any = {}

    def __init__(self):
        self.__envConfig = EnvConfig().get_env_config();
        if self.__envConfig.get("env") == "dev":
            self.__buildConfig = DevConfig.getConfig()
        elif self.__envConfig.get("env") == "prod":
            self.__buildConfig = ProdConfig.getConfig()

    def get(self):
        return {
            **self.__envConfig,
            **self.__buildConfig
        }
