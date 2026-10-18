import json, numpy as np
def box(x0,y0,z0,x1,y1,z1,flip=False):
    v=np.array([[x0,y0,z0],[x1,y0,z0],[x1,y1,z0],[x0,y1,z0],[x0,y0,z1],[x1,y0,z1],[x1,y1,z1],[x0,y1,z1]],float)
    f=np.array([[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]])
    if flip: f=f[:,[0,2,1]]
    return v,f
def build(n_floors=10, fh=3.3, nx=7, ny=4, sp=6.0, flip_frac=0.0, seed=0, drop_vcount=None):
    rng=np.random.default_rng(seed)
    recs=[];V=[];F=[];off=0
    def add(t,v,f,st):
        nonlocal off
        recs.append(dict(index=len(recs),global_id=f"G{len(recs)}",ifc_type=t,name=t,storey=st,section="x",mesh_method="product",
            bbox=dict(min=v.min(0).tolist(),max=v.max(0).tolist()),centroid=v.mean(0).tolist(),volume_m3=0.0,v_start=off,v_count=len(v),f_count=len(f)))
        V.append(v);F.append(f+off);off+=len(v)
    for t in ["IfcBeam","IfcColumn","IfcSlab"]:
        for fl in range(1,n_floors+1):
            z=fl*fh
            if t=="IfcColumn":
                for i in range(nx):
                    for j in range(ny):
                        v,f=box(i*sp-.2,j*sp-.2,z-fh,i*sp+.2,j*sp+.2,z-.12,rng.random()<flip_frac); add(t,v,f,f"T{fl}")
            elif t=="IfcBeam":
                for i in range(nx-1):
                    for j in range(ny):
                        v,f=box(i*sp,j*sp-.15,z-.5,(i+1)*sp,j*sp+.15,z-.12,rng.random()<flip_frac); add(t,v,f,f"T{fl}")
                for i in range(nx):
                    for j in range(ny-1):
                        v,f=box(i*sp-.15,j*sp,z-.5,i*sp+.15,(j+1)*sp,z-.12,rng.random()<flip_frac); add(t,v,f,f"T{fl}")
            else:
                v,f=box(-.5,-.5,z-.12,(nx-1)*sp+.5,(ny-1)*sp+.5,z,rng.random()<flip_frac); add(t,v,f,f"T{fl}")
    Vc=np.vstack(V);Fc=np.vstack(F)
    for r in recs:
        s=r["v_start"];n=r["v_count"]
        vv=Vc[s:s+n];ff=Fc[(Fc[:,0]>=s)&(Fc[:,0]<s+n)]-s
        a,b,c=vv[ff[:,0]],vv[ff[:,1]],vv[ff[:,2]]
        r["volume_m3"]=float(abs(np.einsum("ij,ij->i",a,np.cross(b,c)).sum()/6))
    return recs,Vc.astype(np.float32),Fc.astype(np.int32)
def save(d,**kw):
    import os;os.makedirs(d,exist_ok=True)
    recs,V,F=build(**kw)
    json.dump({"unit":"m","storeys":{},"elements":recs},open(f"{d}/plm_elements.json","w"))
    np.savez_compressed(f"{d}/plm_meshes.npz",verts=V,faces=F)
    return len(recs)
if __name__=="__main__":
    print(save("test/clean",flip_frac=0.0), save("test/flipped",flip_frac=0.5))