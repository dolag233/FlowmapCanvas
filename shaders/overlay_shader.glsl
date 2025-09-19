#version 150
in vec2 TexCoords;
out vec4 FragColor;
uniform sampler2D overlayMap;
uniform float u_opacity;
uniform float u_mainViewScale;
uniform vec2 u_mainViewOffset;
uniform bool u_repeat;
uniform vec2 u_aspectScale;
uniform vec2 u_aspectOffset;
void main(){
    // 覆盖模式：先做纵横比cover校正，再映射到主视图空间
    vec2 corrected = (TexCoords - u_aspectOffset) / u_aspectScale;
    vec2 uv = corrected / u_mainViewScale - u_mainViewOffset;
    if (u_repeat) {
        uv = fract(uv);
    } else {
        // outside domain -> transparent
        if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
            FragColor = vec4(0.0, 0.0, 0.0, 0.0);
            return;
        }
    }
    vec4 c = texture(overlayMap, uv);
    FragColor = vec4(c.rgb, c.a * u_opacity);
}


