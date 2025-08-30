#version 150
out vec4 FragColor;
uniform vec3 u_color;
uniform float u_opacity;
void main(){
    FragColor = vec4(u_color, u_opacity);
}
