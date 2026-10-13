import pandas as pd


#读取POD矩阵

df=pd.read_excel(
    "data/MIDAS_POD_matrix.xlsx"
)


dof=df.iloc[:,0]


rows=[]


for i,name in enumerate(dof):

    text=str(name)

    import re

    if "_" in text:

        eid = text.split("_")[0]

        pos = re.findall(
            r'_(.*?)\[',
            text
        )[0]

        node = re.findall(
            r'\[(.*?)\]',
            text
        )[0]

    else:

        eid = text
        pos = ""
        node = ""

    rows.append({

        "DOF": text,

        "element": eid,

        "position": pos,

        "node": node,

        "index": i

    })


mapping=pd.DataFrame(rows)


mapping.to_csv(
    "data/pod_mapping.csv",
    index=False,
    encoding="utf-8-sig"
)


print("映射生成完成")
print(mapping.head())
print("数量:",len(mapping))