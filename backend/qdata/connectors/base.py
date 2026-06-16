from abc import ABC, abstractmethod

import pandas as pd


class Connector(ABC):
    @abstractmethod
    def load(self, **kwargs) -> pd.DataFrame: ...

    @abstractmethod
    def schema(self) -> list[dict]: ...

    @abstractmethod
    def sample(self, n: int = 100) -> pd.DataFrame: ...
