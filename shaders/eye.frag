#version 330
uniform vec2 u_resolution;
uniform vec2 u_contour[128];
uniform int u_contour_count[2];
uniform float u_contour_mix[2];
uniform float u_eye_opacity[2];
uniform float u_design_aspect;
uniform vec4 u_eye_a[2]; // center xy, base half width / half height
uniform vec4 u_eye_b[2]; // radius, whole bend, top micro curve, bottom micro curve
uniform vec4 u_eye_c[2]; // rotation, geometric bulge, end taper, preservation factor
uniform vec4 u_volume_a; // depth, center fill, bulge influence, side falloff
uniform vec4 u_volume_b; // bottom falloff, edge falloff, AA softness, broad roundness
uniform bool u_flat;
uniform bool u_show_safe;
uniform float u_safe_margin;
out vec4 fragColor;

vec2 inverseRotate(vec2 p,float a) {
    float c=cos(a),s=sin(a);
    return vec2(c*p.x+s*p.y,-s*p.x+c*p.y);
}
float roundedBox(vec2 p,vec2 b,float r) {
    vec2 q=abs(p)-b+r;
    return length(max(q,0.0))+min(max(q.x,q.y),0.0)-r;
}
float contourDistance(vec2 p,vec2 size,int eye,out float cushion) {
    float nearest=1e10;float potential=0.0;bool inside=false;int count=u_contour_count[eye];
    for(int j=0;j<64;j++) {
        if(j>=count) break;
        vec2 a=u_contour[eye*64+j]*size,b=u_contour[eye*64+((j+1)%count)]*size;
        vec2 edge=b-a,w=p-a;
        vec2 delta=w-edge*clamp(dot(w,edge)/max(dot(edge,edge),1e-20),0.0,1.0);
        nearest=min(nearest,dot(delta,delta));
        vec2 normalizedDelta=delta/max(min(size.x,size.y),1e-7);
        potential+=1.0/pow(max(dot(normalizedDelta,normalizedDelta),1e-8),2.0);
        if((a.y>p.y)!=(b.y>p.y)) {
            if(p.x<(b.x-a.x)*(p.y-a.y)/(b.y-a.y)+a.x) inside=!inside;
        }
    }
    cushion=inside?pow(max(potential,1e-8),-0.25):0.0;
    return sqrt(nearest)*(inside?-1.0:1.0);
}
vec3 drawEye(vec2 face,int i,float pixel) {
    if(u_eye_opacity[i]<=0.0) return vec3(0.0);
    vec4 a=u_eye_a[i],b=u_eye_b[i],c=u_eye_c[i];
    vec2 p=inverseRotate(face-a.xy,c.x);
    // Inverse circular deformation. Whole Bend rotates each entire cross-section
    // around one centerline; both silhouette edges and the volume follow it.
    vec2 bent=p;
    if(abs(b.y)>0.0001) {
        float radius=a.z/b.y;
        vec2 radial=vec2(p.x,p.y+radius*cos(b.y));
        float theta=atan(radial.x*sign(radius),radial.y*sign(radius));
        bent=vec2(radius*theta,sign(radius)*length(radial)-radius);
    }
    float x=bent.x/a.z;
    float arch=max(0.0,1.0-x*x);
    float profile=(1.0+c.y*arch)*(1.0-c.z*min(x*x,1.0))*c.w;
    float center=0.5*(b.z+b.w)*arch;
    float thickness=profile+(b.z-b.w)*arch/(2.0*a.w);
    vec2 q=vec2(bent.x,(bent.y-center)/max(thickness,0.03));
    float d=roundedBox(q,a.zw,b.x);
    float cushion=0.0;
    if(u_contour_count[i]>=3) d=mix(d,contourDistance(q,a.zw,i,cushion),u_contour_mix[i]);
    float aa=max(length(vec2(dFdx(d),dFdy(d)))*u_volume_b.z,0.000001);
    float coverage=1.0-smoothstep(-aa,aa,d);

    // A continuous cushion height field in the deformed body's own coordinates.
    // Surface normals, not just a brightness multiplier, carry the volume.
    vec2 n=clamp(q/a.zw,vec2(-1.0),vec2(1.0));
    float power=u_volume_b.w;
    float ax=max(0.001,1.0-pow(abs(n.x),power));
    float ay=max(0.001,1.0-pow(abs(n.y),power));
    float dome=sqrt(ax*ay);
    if(u_contour_count[i]>=3) dome=mix(dome,sqrt(clamp(cushion,0.0,1.0)),u_contour_mix[i]);
    float z=a.w*u_volume_a.x*(0.8+c.y*u_volume_a.z)*dome;
    vec3 normal=normalize(vec3(-dFdx(z)/pixel,-dFdy(z)/pixel,1.0));
    vec3 light=normalize(vec3(-0.22,0.48,1.0));
    float diffuse=max(0.0,dot(normal,light));
    float fill=(0.30+0.48*u_volume_a.y);
    float brightness=fill*(0.50+0.50*diffuse);
    brightness*=1.0-u_volume_a.w*0.62*pow(abs(n.x),3.0);
    brightness*=1.0-u_volume_b.x*0.62*pow(max(-n.y,0.0),2.0);
    brightness*=1.0-u_volume_b.y*0.45*(1.0-dome);
    if(u_volume_a.x<0.85) brightness=mix(fill,brightness,smoothstep(0.0,0.85,u_volume_a.x));
    // A neutral temporary hue; no specular highlight, rim, white spot or bloom.
    if(u_flat) brightness=0.76;
    return vec3(0.91,0.94,0.97)*brightness*coverage*u_eye_opacity[i];
}
void main() {
    float scale=min(u_resolution.y,u_resolution.x/u_design_aspect);
    vec2 face=(gl_FragCoord.xy-u_resolution*0.5)/scale;
    vec3 color=max(drawEye(face,0,1.0/scale),drawEye(face,1,1.0/scale));
    if(u_show_safe) {
        vec2 bounds=vec2(u_design_aspect*.5,.5)-u_safe_margin;
        vec2 d=abs(abs(face)-bounds);
        if((d.x<.75/scale && abs(face.y)<=bounds.y)||(d.y<.75/scale && abs(face.x)<=bounds.x))
            color=vec3(.14,.21,.24);
    }
    fragColor=vec4(color,1.0);
}

