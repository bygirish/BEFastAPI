# get env variables and pass them to dev and prod config files

class EnvConfig:

    __env = ""
    __aws_key = ""
    __aws_secret = ""

    def get_env_config(self) -> dict:
        return {
            "env": self.__env,
            "aws_key": self.__aws_key,
            "aws_secret": self.__aws_secret
        }

