import pandas as pd
import numpy as np


#读取矩阵
df=pd.read_excel(
    "data/MIDAS_POD_matrix.xlsx"
)


#去掉DOF列
X=df.iloc[:,1:].values


print(X.shape)


#均值中心化

mean=np.mean(X,axis=1)

Xc=X-mean[:,None]


#SVD

U,S,V=np.linalg.svd(
    Xc,
    full_matrices=False
)


#保留前r阶

r=10

Ur=U[:,:r]


np.save(
    "data/pod_basis.npy",
    Ur
)

np.save(
    "data/pod_mean.npy",
    mean
)


print("POD训练完成")
print("保留阶数:",r)
