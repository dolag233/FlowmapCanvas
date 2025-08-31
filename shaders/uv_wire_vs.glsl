#version 150
in vec2 aUV;
uniform float u_mainViewScale;
uniform vec2 u_mainViewOffset;
void main(){
    // Forward mapping from sample UV to screen texcoords:
    // TexCoords = (aUV + u_mainViewOffset) * u_mainViewScale
    vec2 tex = (aUV + u_mainViewOffset) * u_mainViewScale;
    vec2 clip = vec2(tex.x * 2.0 - 1.0, tex.y * 2.0 - 1.0);
    gl_Position = vec4(clip, 0.0, 1.0);
}
