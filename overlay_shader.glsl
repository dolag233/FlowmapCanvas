#version 150
in vec2 TexCoords;
out vec4 FragColor;
uniform sampler2D overlayMap;
uniform float u_opacity;
uniform float u_mainViewScale;
uniform vec2 u_mainViewOffset;
uniform bool u_repeat;
void main(){
    // Map screen TexCoords into the main view's texture space
    vec2 uv = TexCoords / u_mainViewScale - u_mainViewOffset;
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


