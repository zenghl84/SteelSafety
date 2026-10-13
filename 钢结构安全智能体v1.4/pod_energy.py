import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

plt.rcParams['font.family'] = ['Times New Roman', 'Microsoft YaHei', 'serif']

df=pd.read_excel(
    "data/MIDAS_POD_matrix.xlsx"
)


X=df.iloc[:,1:].values


#中心化
mean=np.mean(X,axis=1)
Xc=X-mean[:,None]


#SVD
U,S,V=np.linalg.svd(
    Xc,
    full_matrices=False
)


energy=S**2/np.sum(S**2)

cum=np.cumsum(energy)


for i in range(len(cum)):
    print(
        f"阶数 {i+1}: 能量占比 {cum[i]*100:.3f}%"
    )


plt.figure(figsize=(8,5))
plt.plot(
    range(1,len(cum)+1),
    cum*100,
    marker='o'
)

plt.xlabel("POD modes")
plt.ylabel("Cumulative energy (%)")
plt.grid()

plt.show()
