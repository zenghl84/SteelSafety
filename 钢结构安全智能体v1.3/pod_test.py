import pandas as pd
import numpy as np


#读取原始矩阵

df=pd.read_excel(
    "data/MIDAS_POD_matrix.xlsx"
)


X=df.iloc[:,1:].values


#读取POD模型

U=np.load(
    "data/pod_basis.npy"
)

mean=np.load(
    "data/pod_mean.npy"
)


#随机测试第几个施工阶段
index=5


#原始响应

x=X[:,index]


#降阶

a=U.T@(x-mean)


#恢复

xr=mean+U@a


#误差

error=np.linalg.norm(x-xr)/np.linalg.norm(x)


print("================")
print("测试工况:",index)
print("POD误差:",error)
print("保留阶数:",U.shape[1])