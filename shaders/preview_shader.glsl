#version 150
in vec2 TexCoords;
out vec4 FragColor;
uniform sampler2D flowMap;
uniform vec2 u_previewOffset;
uniform bool u_previewRepeat;
void main(){
    vec2 uv = TexCoords - u_previewOffset;
    if (u_previewRepeat) {
        uv = fract(uv);
    }
    if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
        FragColor = vec4(0.1,0.1,0.1,1.0);
        return;
    }
    vec4 flow = texture(flowMap, uv);
    FragColor = vec4(flow.rg, 0.0, 0.75);
}

