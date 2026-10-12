import numpy as np
import pandas as pd


# 读取POD恢复结果
# 这里先模拟，后面接入app时替换

U=np.load(
    "data/pod_basis.npy"
)

mean=np.load(
    "data/pod_mean.npy"
)


# 测试POD系数
a=np.zeros(U.shape[1])


response=mean+U@a


# 读取映射

mapping=pd.read_csv(
    "data/pod_mapping.csv"
)


mapping["response"]=response[
    mapping["index"]
]


# 按杆件聚合

element_response=mapping.groupby(
    "element"
)["response"].apply(
    lambda x: np.mean(np.abs(x))
)


element_response=pd.DataFrame(
    element_response
)


element_response.columns=[
    "stress"
]


element_response.to_csv(
    "data/element_stress.csv"
)


print("杆件响应生成完成")

print(
    element_response.head()
)

print(
    "杆件数量:",
    len(element_response)
)