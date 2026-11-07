# Original export-survival edits recovered from session history

These diffs record source edits made on 4 November 2026. They are historical evidence, not instructions to revert entire files: subsequent animation and other changes must be preserved. The timestamps below are UTC.

## 2026-11-04T14:01:54.482Z — invertebrates.py

```diff
@@ -7,3 +7,3 @@
     for side in (-1, 1):
-        mesh.ellipsoid((x+.075,y+side*.042,z+.035), (.016,.014,.015), 'fish_dark', 8, 5)
+        mesh.ellipsoid((x+.075,y+side*.042,z+.035), (.022,.020,.021), 'fish_dark', 8, 5)
         for i in range(4):
@@ -11,3 +11,3 @@
             mesh.swept_tube([(px,y+side*.05,z), (px-.025,y+side*.12,z+.01),
-                             (px-.04,y+side*.15,z-.045)], .010, 'sponge', 5)
+                             (px-.04,y+side*.15,z-.045)], .016, 'sponge', 5)
         mesh.swept_tube([(x+.07,y+side*.04,z), (x+.14,y+side*.09,z+.04)], .014, 'sponge', 5)
@@ -17,3 +17,3 @@
                              (x+.20,y+side*.09+finger*.018,z+.055),
-                             (x+.215,y+side*.09+finger*.009,z+.06)], .009, 'sponge', 5)
+                             (x+.215,y+side*.09+finger*.009,z+.06)], .016, 'sponge', 5)
```

## 2026-11-04T14:03:45.295Z — invertebrates.py

```diff
@@ -27,9 +27,9 @@
     for side in (-1, 1):
-        mesh.ellipsoid((x+.095,y+side*.038,z+.035), (.014,.012,.014), 'fish_dark', 8, 5)
+        mesh.ellipsoid((x+.095,y+side*.038,z+.035), (.022,.020,.022), 'fish_dark', 8, 5)
         for i in range(4):
             px = x - .04*i
-            mesh.swept_tube([(px,y+side*.035,z-.02), (px+.025,y+side*.11,z-.08)], .005, 'sand', 4)
-        mesh.swept_tube([(x+.10,y+side*.025,z+.02), (x+.30,y+side*.14,z+.13)], .003, 'sand', 4)
-        mesh.swept_tube([(x+.07,y+side*.04,z), (x+.18,y+side*.12,z-.02)], .01, 'sponge', 4)
-        mesh.swept_tube([(x+.18,y+side*.12,z-.02), (x+.22,y+side*.14,z-.01)], .009, 'sand', 5)
+            mesh.swept_tube([(px,y+side*.035,z-.02), (px+.025,y+side*.11,z-.08)], .014, 'sand', 4)
+        mesh.swept_tube([(x+.10,y+side*.025,z+.02), (x+.30,y+side*.14,z+.13)], .012, 'sand', 4)
+        mesh.swept_tube([(x+.07,y+side*.04,z), (x+.18,y+side*.12,z-.02)], .014, 'sponge', 4)
+        mesh.swept_tube([(x+.18,y+side*.12,z-.02), (x+.22,y+side*.14,z-.01)], .016, 'sand', 5)
     for side in (-1, 1):
```

## 2026-11-04T14:06:06.720Z — life.py

```diff
@@ -208,3 +208,3 @@
                        p[2] + sign*length*math.cos(a) + .025*t)
-                mesh.swept_tube([p, tip], .007, 'polyp', 5)
+                mesh.swept_tube([p, tip], .013, 'polyp', 5)
```

## 2026-11-04T14:07:42.524Z — life.py

```diff
@@ -173,3 +173,3 @@
                         root_x = cx + direction*width*(.28 + .24*ray)
-                        tip_x = root_x + direction*(.018 + .006*ray)*(1-tier/7)
+                        tip_x = root_x + direction*(.030 + .008*ray)*(1-tier/7)
                         mesh.face([(root_x, wy-.026, z0),
```

## 2026-11-04T14:09:22.497Z — life.py

```diff
@@ -61,3 +61,3 @@
                    tip[2] - side*.045*math.cos(a) + .035*math.sin(a))
-            mesh.swept_tube([points[-2],tip,end], .009, 'coralline', 5)
+            mesh.swept_tube([points[-2],tip,end], .013, 'coralline', 5)
     for i in range(12):
@@ -69,3 +69,3 @@
                       (a[2]+b[2])/2 + .018 * math.sin(i*3+j))
-            mesh.swept_tube([a, middle, b], .009, 'coralline', 4)
+            mesh.swept_tube([a, middle, b], .013, 'coralline', 4)
```

## 2026-11-04T14:12:01.688Z — invertebrates.py

```diff
@@ -7,3 +7,5 @@
     for side in (-1, 1):
-        mesh.ellipsoid((x+.075,y+side*.042,z+.035), (.022,.020,.021), 'fish_dark', 8, 5)
+        eye_y = y+side*.064
+        mesh.face([(x+.056,eye_y,z+.018), (x+.094,eye_y,z+.018),
+                   (x+.094,eye_y,z+.052), (x+.056,eye_y,z+.052)], 'fish_dark')
         for i in range(4):
```

## 2026-11-04T14:13:22.327Z — invertebrates.py

```diff
@@ -29,3 +29,5 @@
     for side in (-1, 1):
-        mesh.ellipsoid((x+.095,y+side*.038,z+.035), (.022,.020,.022), 'fish_dark', 8, 5)
+        eye_y = y+side*.054
+        mesh.face([(x+.076,eye_y,z+.019),(x+.114,eye_y,z+.019),
+                   (x+.114,eye_y,z+.053),(x+.076,eye_y,z+.053)], 'fish_dark')
         for i in range(4):
```

## 2026-11-04T14:15:06.184Z — invertebrates.py

```diff
@@ -15,3 +15,3 @@
         mesh.swept_tube([(x+.07,y+side*.04,z), (x+.14,y+side*.09,z+.04)], .014, 'sponge', 5)
-        mesh.ellipsoid((x+.15,y+side*.09,z+.04), (.035,.025,.025), 'sponge', 10, 6)
+        mesh.ellipsoid((x+.15,y+side*.09,z+.04), (.048,.036,.037), 'sponge', 10, 6)
         for finger in (-1, 1):
```

## 2026-11-04T14:16:55.188Z — invertebrates.py

```diff
@@ -50,4 +50,4 @@
     mesh.swept_tube([(x+.015,y-.07,z+.035), (x+.025,y,z+.018),
-                     (x+.015,y+.07,z+.035)], .012, 'sand', 6)
-    mesh.ellipsoid((x+.05,y,z+.035), (.085,.075,.05), 'sponge', 10, 6)
+                     (x+.015,y+.07,z+.035)], .016, 'sand', 6)
+    mesh.ellipsoid((x+.05,y,z+.035), (.10,.09,.065), 'sponge', 10, 6)
     for side in (-1,1):
```

## 2026-11-04T14:17:50.946Z — invertebrates.py

```diff
@@ -55,2 +55,2 @@
             px=x+i*.035
-            mesh.swept_tube([(px,y+side*.045,z+.025), (px+.045,y+side*.12,z)], .008, 'sponge', 4)
+            mesh.swept_tube([(px,y+side*.045,z+.025), (px+.045,y+side*.12,z)], .014, 'sponge', 4)
```

## 2026-11-04T14:23:48.542Z — fishes.py

```diff
@@ -5,4 +5,9 @@
 def _disc(mesh, x, y, z, r, color):
-    mesh.face([(x + r * math.cos(math.tau * i / 12), y,
-                z + r * math.sin(math.tau * i / 12)) for i in range(12)], color)
+    # A center fan avoids the tiny ear triangles produced when the exporter
+    # triangulates small n-gons. Preserve visible marks at the minimum size.
+    r = max(r, .016)
+    edge = [(x + r * math.cos(math.tau * i / 8), y,
+             z + r * math.sin(math.tau * i / 8)) for i in range(8)]
+    for i in range(8):
+        mesh.face([(x,y,z),edge[i],edge[(i+1)%8]], color)
```

## 2026-11-04T14:26:07.489Z — life.py

```diff
@@ -112,7 +112,8 @@
                 continue
-            radius = .009 + .003*(1+math.sin(column*3.1+row))/2
+            radius = .017 + .003*(1+math.sin(column*3.1+row))/2
             points = [(x+px+radius*math.cos(math.tau*i/8),
-                       y+py+radius*.8*math.sin(math.tau*i/8),z+.151)
+                       y+py+radius*math.sin(math.tau*i/8),z+.151)
                       for i in range(8)]
-            mesh.face(points, 'fish_white')
+            for i in range(8):
+                mesh.face([(x+px,y+py,z+.151),points[i],points[(i+1)%8]], 'fish_white')
```

## 2026-11-04T14:27:49.672Z — life.py

```diff
@@ -137,3 +137,3 @@
                    pz+.135+.007*math.sin(i+tentacle))
-            mesh.swept_tube([start,end], .009, 'zoanthid', 5)
+            mesh.swept_tube([start,end], .013, 'zoanthid', 5)
```

## 2026-11-04T14:29:51.118Z — life.py

```diff
@@ -34,3 +34,3 @@
         end = (x + .92*radius*math.cos(angle),y + .92*radius*math.sin(angle),z + height*1.12)
-        mesh.swept_tube([start,end], .009, 'polyp', 5)
+        mesh.swept_tube([start,end], .013, 'polyp', 5)
```

## 2026-11-04T14:31:24.226Z — life.py

```diff
@@ -230,3 +230,3 @@
         ridge = [point(a,f) for f in (.12,.4,.7,.95)]
-        mesh.swept_tube([(p[0],p[1],p[2]+.008) for p in ridge], .010, 'polyp', 5)
+        mesh.swept_tube([(p[0],p[1],p[2]+.008) for p in ridge], .013, 'polyp', 5)
```

## 2026-11-04T14:33:24.433Z — life.py

```diff
@@ -93,3 +93,3 @@
             a, b, c = section(i)
-            mesh.swept_tube([a, b, c], .008, 'sand', 4)
+            mesh.swept_tube([a, b, c], .013, 'sand', 4)
     center_point = (x, y, z + .125)
```

## 2026-11-04T14:33:56.180Z — life.py

```diff
@@ -93,3 +93,3 @@
             a, b, c = section(i)
-            mesh.swept_tube([a, b, c], .013, 'sand', 4)
+            mesh.swept_tube([a, b, c], .018, 'sand', 4)
     center_point = (x, y, z + .125)
```

## 2026-11-04T14:34:31.014Z — life.py

```diff
@@ -93,3 +93,3 @@
             a, b, c = section(i)
-            mesh.swept_tube([a, b, c], .018, 'sand', 4)
+            mesh.swept_tube([a, b, c], .013, 'sand', 4)
     center_point = (x, y, z + .125)
```

## 2026-11-04T14:38:19.627Z — corals.py

```diff
@@ -110,3 +110,3 @@
                    tip[2]+.018+.008*math.sin(3*a))
-            mesh.swept_tube([tip,end], .010, 'flowerpot_tip', 5)
+            mesh.swept_tube([tip,end], .013, 'flowerpot_tip', 5)
     x,y,z = (4.0, -.72, 2.76)
```

## 2026-11-04T14:40:36.653Z — corals.py

```diff
@@ -133,3 +133,3 @@
                    start[2]+.045+.012*math.sin(i*2.1))
-            mesh.swept_tube([start,end], .010, 'flowerpot_tip', 5)
+            mesh.swept_tube([start,end], .013, 'flowerpot_tip', 5)
```
