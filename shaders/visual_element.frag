#version 330
// Independent overlay pass. No eye shape/material uniforms.
uniform vec2 u_resolution;
uniform float u_design_aspect;
uniform float u_safe_margin;
uniform vec2 u_position;
uniform float u_scale;
uniform float u_rotation;
uniform float u_opacity;
uniform vec2 u_points[40];
uniform int u_count;
uniform float u_stroke;
uniform vec3 u_dot;
uniform vec3 u_color;
uniform vec4 u_bounds; // x min/max, y min/max in face coordinates
uniform bool u_show_bounds;
out vec4 fragColor;
float segmentDistance(vec2 p,vec2 a,vec2 b) {
    vec2 v=b-a;
    float t=clamp(dot(p-a,v)/max(dot(v,v),1e-12),0.0,1.0);
    return length(p-a-t*v);
}
void main() {
    float pixels=min(u_resolution.y,u_resolution.x/u_design_aspect);
    vec2 face=(gl_FragCoord.xy-u_resolution*.5)/pixels;
    vec2 safe=vec2(u_design_aspect*.5,.5)-u_safe_margin;
    // Final pixel guard for AA and unusually small previews.
    if(any(greaterThan(abs(face),safe))) discard;
    float pad=2.0/pixels;
    if(face.x<u_bounds.x-pad || face.x>u_bounds.y+pad ||
       face.y<u_bounds.z-pad || face.y>u_bounds.w+pad) discard;
    vec2 p=face-u_position;
    float c=cos(u_rotation),s=sin(u_rotation);
    p=vec2(c*p.x+s*p.y,-s*p.x+c*p.y)/u_scale;
    float d=length(p-u_dot.xy)-u_dot.z;
    for(int i=0;i<39;i++) {
        if(i>=u_count-1) break;
        d=min(d,segmentDistance(p,u_points[i],u_points[i+1])-u_stroke);
    }
    float aa=.8/(pixels*u_scale);
    float coverage=1.0-smoothstep(-aa,aa,d);
    float alpha=coverage*u_opacity;
    vec3 color=u_color;
    if(u_show_bounds) {
        vec2 center=vec2(u_bounds.x+u_bounds.y,u_bounds.z+u_bounds.w)*.5;
        vec2 halfsize=vec2(u_bounds.y-u_bounds.x,u_bounds.w-u_bounds.z)*.5;
        vec2 q=abs(face-center)-halfsize;
        float boxDistance=length(max(q,0.0))+min(max(q.x,q.y),0.0);
        float line=1.0-smoothstep(.35/pixels,1.1/pixels,abs(boxDistance));
        color=mix(color,vec3(.18,.70,.48),line);
        alpha=max(alpha,line*.8);
    }
    fragColor=vec4(color,alpha);
}

