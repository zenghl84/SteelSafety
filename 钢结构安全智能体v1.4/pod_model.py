import numpy as np


# 加载POD模型
import numpy as np
from pathlib import Path


BASE_DIR = Path(__file__).parent


U = np.load(
    BASE_DIR / "data" / "pod_basis.npy"
)


mean = np.load(
    BASE_DIR / "data" / "pod_mean.npy"
)


def reconstruct(a):
    """
    根据POD系数恢复结构响应

    参数:
    a : list 或 numpy数组
        POD系数

    返回:
    x : numpy数组
        恢复后的结构响应
    """

    a = np.array(a)

    x = mean + U @ a

    return x


def get_dimension():

    return U.shape[1]