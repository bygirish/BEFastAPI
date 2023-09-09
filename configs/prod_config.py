class ProdConfig:
    __api_url: str = ""

    def getConfig(self):
        return {
            "api_url": self.__api_url
        }
