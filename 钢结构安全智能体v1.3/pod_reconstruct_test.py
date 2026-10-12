from pod_model import reconstruct,get_dimension
import numpy as np


print("当前POD阶数:")
print(get_dimension())


# 随便给一个10阶系数
a=np.random.randn(10)


x=reconstruct(a)


print("恢复响应维度:")
print(x.shape)


print("最大响应:")
print(np.max(x))


print("最小响应:")
print(np.min(x))