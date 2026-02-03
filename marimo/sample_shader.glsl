// Shadertoy version
// Copy and paste into https://www.shadertoy.com/new

const mat3 m = mat3( 0.00,  0.80,  0.60,
                    -0.80,  0.36, -0.48,
                    -0.60, -0.48,  0.64 );

float hash(float n) {
    return fract(sin(n)*43758.5453);
}

float noise(in vec3 x) {
    vec3 p = floor(x);
    vec3 f = fract(x);
    f = f*f*(3.0 - 2.0*f);
    float n = p.x + p.y*57.0 + 113.0*p.z;
    float res = mix(mix(mix(hash(n + 0.0), hash(n + 1.0), f.x),
                        mix(hash(n + 57.0), hash(n + 58.0), f.x), f.y),
                    mix(mix(hash(n + 113.0), hash(n + 114.0), f.x),
                        mix(hash(n + 170.0), hash(n + 171.0), f.x), f.y), f.z);
    return res;
}

float fbm(vec3 p) {
    float f;
    f = 0.5 * noise(p); p = m * p * 2.02;
    f += 0.25 * noise(p); p = m * p * 2.03;
    f += 0.125 * noise(p); p = m * p * 2.01;
    f += 0.0625 * noise(p);
    return f;
}

#define snoise(x) (2.0*noise(x)-1.0)

float sfbm(vec3 p) {
    float f;
    f = 0.5 * snoise(p); p = m * p * 2.02;
    f += 0.25 * snoise(p); p = m * p * 2.03;
    f += 0.125 * snoise(p); p = m * p * 2.01;
    f += 0.0625 * snoise(p);
    return f;
}

#define sfbm3(p) vec3(sfbm(p), sfbm(p - 327.67), sfbm(p + 327.67))

void mainImage( out vec4 fragColor, in vec2 fragCoord )
{
    // Normalized pixel coordinates (centered and aspect corrected)
    float aspect = iResolution.x / iResolution.y;
    vec2 p = (fragCoord / iResolution.y) - vec2(0.5 * aspect, 0.5);

    // Camera setup
    vec3 ro = vec3(0.0, 0.0, 10.0);
    vec3 rd = normalize(vec3(p * vec2(aspect, 1.0), -1.5));

    // Rotate camera slowly around Y axis
    float angle = iTime * 0.2;
    float c = cos(angle);
    float s = sin(angle);
    ro.xz = vec2(c * ro.x - s * ro.z, s * ro.x + c * ro.z);
    rd.xz = vec2(c * rd.x - s * rd.z, s * rd.x + c * rd.z);

    vec4 col = vec4(0.0, 0.0, 0.0, 1.0);

    float t = 0.0;
    float maxDist = 20.0;
    float minDist = 0.01;
    float glow = 0.0;

    for (int i = 0; i < 100; i++) {
        if (t > maxDist || col.r > 0.99) break;

        vec3 pos = ro + rd * t;

        // Create wave-like overlapping lines using sine and fbm
        float wave = abs(sin(pos.x * 3.0 + iTime) * cos(pos.y * 3.0 + iTime * 0.5));

        // Add fine detailed lines with fbm noise
        float detail = fbm(pos * 3.0 + vec3(iTime * 0.5));

        // Distance field for lines: sharp edges where wave + detail crosses threshold
        float lineDist = abs(wave + detail * 0.3 - 0.5);

        // Emphasize sharp edges
        float edge = smoothstep(0.01, 0.0, lineDist);

        // Accumulate glow for bright white lines
        glow += edge * 0.05;

        // Ray marching step size influenced by line distance
        t += max(minDist, lineDist * 0.5);
    }

    glow = clamp(glow, 0.0, 1.0);

    // Final color: black background with white glowing lines
    fragColor = vec4(vec3(glow), 1.0);
}
