#version 150
in vec2 aUV;
uniform float u_mainViewScale;
uniform vec2 u_mainViewOffset;
uniform vec2 u_aspectScale;
uniform vec2 u_aspectOffset;
void main(){
    // 覆盖模式：内容->屏幕（cover）
    vec2 tex = (aUV + u_mainViewOffset) * u_mainViewScale;
    tex = tex * u_aspectScale + u_aspectOffset;
    vec2 clip = vec2(tex.x * 2.0 - 1.0, tex.y * 2.0 - 1.0);
    gl_Position = vec4(clip, 0.0, 1.0);
}
