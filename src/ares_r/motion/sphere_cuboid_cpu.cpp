// Independent double-precision distance kernel. No fast-math, no geometry culling.
#include <cmath>
#include <limits>
#include <algorithm>
extern "C" void sphere_cuboid_cpu(const double* centers, const double* radii,
 const double* boxes, int samples, int spheres, int count,
 double* gaps, int* indices, double* trace) {
 const double inf=std::numeric_limits<double>::infinity();
 for(int n=0;n<samples;++n) trace[n]=inf;
 for(int b=0;b<count;++b){
  const double* box=boxes+15*b; double best=inf; int best_index=0;
  for(int n=0;n<samples;++n) for(int s=0;s<spheres;++s){
   const double* p=centers+3*(n*spheres+s);
   const double x=p[0]-box[0],y=p[1]-box[1],z=p[2]-box[2];
   const double dx=std::abs(x*box[3]+y*box[6]+z*box[9])-box[12]*.5;
   const double dy=std::abs(x*box[4]+y*box[7]+z*box[10])-box[13]*.5;
   const double dz=std::abs(x*box[5]+y*box[8]+z*box[11])-box[14]*.5;
   const double m=std::max(dx,std::max(dy,dz)),r=radii[s];
   // max(axis signed gap)-radius is a lower bound on exact SDF.
   // Skip only if neither requested minimum can improve; no samples removed.
   if(m-r>=best && m-r>=trace[n])continue;
   const double ax=std::max(dx,0.),ay=std::max(dy,0.),az=std::max(dz,0.);
   const double d=std::sqrt(ax*ax+ay*ay+az*az)+std::min(m,0.)-r;
   if(d<best){best=d;best_index=n*spheres+s;}
   if(d<trace[n])trace[n]=d;
  }
  gaps[b]=best;indices[b]=best_index;
 }
}
