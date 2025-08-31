#version 330
out vec4 FragColor;

in vec2 TexCoords;

uniform sampler2D flowMap;
uniform sampler2D baseMap;
uniform bool u_hasBaseMap = false;
uniform float u_flowSpeed = 1.0;
uniform float u_flowDistortion = 0.1;
uniform float u_time = 0.0;
uniform bool u_previewRepeat = false;
uniform float u_mainViewScale = 1.0;
uniform vec2 u_mainViewOffset = vec2(0.0, 0.0);
uniform float u_useDirectX = 0;
uniform float u_scale = 1.0;

void main()
{
    // 应用主视图的缩放和偏移
    vec2 mainTexCoords = TexCoords / u_mainViewScale - u_mainViewOffset;
    vec2 backgroundTexCoords = mainTexCoords / u_scale;
    
    if (u_hasBaseMap) {
        // 处理主视图区域
        vec2 sampleCoords;
        vec2 backgroundSampleCoords = fract(backgroundTexCoords);
        bool showBorder = false;
        bool inRange = true;
        
        if (u_previewRepeat) {
            // 启用重复模式下，使用取模运算实现重复纹理
            sampleCoords = fract(mainTexCoords);
            
            // 检查是否在原始区域的边界上，如果是则绘制黄色边框
            float borderWidth = 0.002;
            if ((mainTexCoords.x >= 0.0 && mainTexCoords.x <= 1.0 && 
                mainTexCoords.y >= 0.0-borderWidth && mainTexCoords.y <= 0.0+borderWidth) ||
                (mainTexCoords.x >= 0.0 && mainTexCoords.x <= 1.0 && 
                mainTexCoords.y >= 1.0-borderWidth && mainTexCoords.y <= 1.0+borderWidth) ||
                (mainTexCoords.y >= 0.0 && mainTexCoords.y <= 1.0 && 
                mainTexCoords.x >= 0.0-borderWidth && mainTexCoords.x <= 0.0+borderWidth) ||
                (mainTexCoords.y >= 0.0 && mainTexCoords.y <= 1.0 && 
                mainTexCoords.x >= 1.0-borderWidth && mainTexCoords.x <= 1.0+borderWidth)) {
                showBorder = true;
                FragColor = vec4(1.0, 1.0, 0.0, 1.0); // 黄色边框
                return;
            }
        } else {
            // 非重复模式，检查是否在[0,1]范围内
            if(mainTexCoords.x < 0.0 || mainTexCoords.x > 1.0 || 
               mainTexCoords.y < 0.0 || mainTexCoords.y > 1.0) {
                // 超出范围，显示黑色背景
                FragColor = vec4(0.1, 0.1, 0.1, 1.0);
                inRange = false;
            }
            
            sampleCoords = mainTexCoords;
        }

        if(inRange){
            // 获取流向向量 - 直接从纹理中读取RG值并转换为[-1,1]范围
            // 注意：Y值已经在CPU中根据当前API模式做了反转处理
            vec2 flowDir = texture(flowMap, sampleCoords).rg * 2.0 - 1.0;
            if(u_useDirectX >= 1)
                flowDir.y *= -1;

            // 执行双样本流动效果处理
            float phaseTime = u_time * u_flowSpeed;

            // 两个错开的相位，相差0.5
            float phase0 = fract(phaseTime);
            float phase1 = fract(phaseTime + 0.5);

            // 相位0的流动偏移
            vec2 offset0 = flowDir * phase0 * u_flowDistortion;
            // 相位1的流动偏移
            vec2 offset1 = flowDir * phase1 * u_flowDistortion;

            // 采样两次纹理
            vec4 color0, color1;

            if (u_previewRepeat) {
                // 重复模式下，确保对纹理的采样也使用取模运算
                color0 = texture(baseMap, fract(backgroundSampleCoords + offset0));
                color1 = texture(baseMap, fract(backgroundSampleCoords + offset1));
            } else {
                // 非重复模式，检查偏移后的坐标是否超出范围
                vec2 samplePos0 = backgroundSampleCoords + offset0;
                vec2 samplePos1 = backgroundSampleCoords + offset1;

                // 对于超出范围的样本，我们可以选择夹紧或丢弃
                samplePos0 = clamp(samplePos0, 0.0, 1.0);
                samplePos1 = clamp(samplePos1, 0.0, 1.0);

                color0 = texture(baseMap, samplePos0);
                color1 = texture(baseMap, samplePos1);
            }

            // 基于相位计算混合权重 - 使用三角函数让过渡更自然
            float weight = abs((0.5 - phase0) / 0.5);

            // 混合两个颜色样本
            FragColor = mix(color0, color1, weight);
        }
    } else {
        // 当没有底图时的处理
        
        if (u_previewRepeat) {
            // 重复模式，使用取模运算
            vec2 repeatedCoord = fract(mainTexCoords);
            FragColor = vec4(texture(flowMap, repeatedCoord).rg, 0.0, 1.0);
            
            // 检查是否在原始区域的边界上，如果是则绘制黄色边框
            float borderWidth = 0.002;
            if ((mainTexCoords.x >= 0.0 && mainTexCoords.x <= 1.0 && 
                mainTexCoords.y >= 0.0-borderWidth && mainTexCoords.y <= 0.0+borderWidth) ||
                (mainTexCoords.x >= 0.0 && mainTexCoords.x <= 1.0 && 
                mainTexCoords.y >= 1.0-borderWidth && mainTexCoords.y <= 1.0+borderWidth) ||
                (mainTexCoords.y >= 0.0 && mainTexCoords.y <= 1.0 && 
                mainTexCoords.x >= 0.0-borderWidth && mainTexCoords.x <= 0.0+borderWidth) ||
                (mainTexCoords.y >= 0.0 && mainTexCoords.y <= 1.0 && 
                mainTexCoords.x >= 1.0-borderWidth && mainTexCoords.x <= 1.0+borderWidth)) {
                FragColor = vec4(1.0, 1.0, 0.0, 1.0); // 黄色边框
            }
        } else {
            // 非重复模式，检查是否在[0,1]范围内
            if(mainTexCoords.x >= 0.0 && mainTexCoords.x <= 1.0 && 
               mainTexCoords.y >= 0.0 && mainTexCoords.y <= 1.0) {
                FragColor = vec4(texture(flowMap, mainTexCoords).rg, 0.0, 1.0);
            } else {
                // 超出范围，显示黑色背景
                FragColor = vec4(0.1, 0.1, 0.1, 1.0);
            }
        }
    }
}