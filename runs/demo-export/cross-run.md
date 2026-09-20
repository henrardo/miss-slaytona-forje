# Cross-run summary

Append-only. A run counts toward "clearly working" only when `counts` is `yes`: the arms differed by the skill alone.

| run | gpu | skill v | skill tok | arm | passed | attempts | converged | attempt tok (in/out) | distil tok (in/out) | turns | attempt s | distil s | steps | counts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| swarm-1789649753 | 1x NVIDIA H200, 143771 MiB | 0 | 565 | cold | 0 | 1 | yes | 3,915,049/12,278 | 0/0 | 102 | 168 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789649753 | 1x NVIDIA H200, 143771 MiB | 0 | 565 | warm | 0 | 1 | yes | 1,745,783/6,958 | 0/0 | 60 | 131 | 0 | 58 (39 w/ reasoning) | yes |
| swarm-1789650709 | 1x NVIDIA H200, 143771 MiB | 0 | 565 | warm | 0 | 0 | no | 0/0 | 0/0 | 0 | 0 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789651145 | 1x NVIDIA H200, 143771 MiB | 0 | 565 | cold | 32 | 3 | no | 6,229,443/23,545 | 0/0 | 194 | 371 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789651145 | 1x NVIDIA H200, 143771 MiB | 0 | 565 | warm | 33 | 1 | yes | 2,866,942/11,733 | 219,952/6,223 | 81 | 180 | 55 | 79 (50 w/ reasoning) | yes |
| swarm-1789657795 | 1x NVIDIA H200, 143771 MiB | 1 | 1718 | cold | 33 | 1 | yes | 2,420,168/8,858 | 0/0 | 79 | 120 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789657795 | 1x NVIDIA H200, 143771 MiB | 1 | 1718 | warm | 33 | 1 | yes | 1,293,678/6,492 | 437,601/12,632 | 52 | 84 | 54 | 50 (27 w/ reasoning) | yes |
| swarm-1789659129 | 1x NVIDIA H200, 143771 MiB | 1 | 1718 | cold | 33 | 2 | yes | 3,250,492/15,759 | 0/0 | 121 | 200 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789659129 | 1x NVIDIA H200, 143771 MiB | 1 | 1718 | warm | 33 | 1 | yes | 1,985,754/9,746 | 731,877/19,629 | 69 | 155 | 75 | 67 (40 w/ reasoning) | yes |
| swarm-1789660694 | 1x NVIDIA H200, 143771 MiB | 1 | 1718 | cold | 32 | 3 | no | 4,937,582/23,419 | 0/0 | 161 | 372 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789660694 | 1x NVIDIA H200, 143771 MiB | 1 | 1718 | warm | 33 | 2 | yes | 2,643,247/13,877 | 1,003,990/27,960 | 106 | 185 | 75 | 102 (63 w/ reasoning) | yes |
| swarm-1789662435 | 1x NVIDIA H200, 143771 MiB | 3 | 989 | cold | 33 | 1 | yes | 3,821,201/14,236 | 0/0 | 100 | 193 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789662435 | 1x NVIDIA H200, 143771 MiB | 3 | 989 | warm | 33 | 1 | yes | 669,592/4,850 | 1,165,154/31,697 | 37 | 146 | 36 | 35 (12 w/ reasoning) | yes |
| swarm-1789663818 | 1x NVIDIA H200, 143771 MiB | 4 | 1538 | cold | 33 | 1 | yes | 1,905,355/7,316 | 0/0 | 65 | 106 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789663818 | 1x NVIDIA H200, 143771 MiB | 4 | 1538 | warm | 33 | 1 | yes | 1,944,739/8,044 | 1,417,150/37,910 | 66 | 110 | 54 | 64 (44 w/ reasoning) | yes |
| swarm-1789666583 | 1x NVIDIA H200 | 4 | 1538 | cold | 32 | 1 | no | 3,040,259/12,537 | 0/0 | 87 | 372 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789666583 | 1x NVIDIA H200 | 4 | 1538 | warm | 33 | 1 | yes | 426,605/3,500 | 0/0 | 27 | 50 | 29 | 25 (9 w/ reasoning) | yes |
| swarm-1789666583 | 1x NVIDIA H200, 143771 MiB | 4 | 1538 | cold | 32 | 1 | no | 3,040,259/12,537 | 0/0 | 87 | 372 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789666583 | 1x NVIDIA H200, 143771 MiB | 4 | 1538 | warm | 33 | 1 | yes | 426,605/3,500 | 1,417,150/37,910 | 27 | 50 | 29 | 25 (9 w/ reasoning) | yes |
| swarm-1789674746 | 1x NVIDIA H200, 143771 MiB | 0 | 565 | warm | 33 | 1 | yes | 3,438,442/12,297 | 1,417,150/37,910 | 93 | 208 | 0 | 91 (67 w/ reasoning) | yes |
| swarm-1789675523 | 1x NVIDIA H200, 143771 MiB | 5 | 1647 | warm | 33 | 1 | yes | 1,594,312/6,424 | 1,417,150/37,910 | 58 | 102 | 0 | 56 (24 w/ reasoning) | yes |
| swarm-1789676178 | 1x NVIDIA H200, 143771 MiB | 5 | 1647 | warm | 33 | 1 | yes | 2,343,619/8,297 | 1,417,150/37,910 | 71 | 130 | 0 | 69 (41 w/ reasoning) | yes |
| swarm-1789676865 | 1x NVIDIA H200, 143771 MiB | 0 | 565 | warm | 33 | 1 | yes | 2,571,991/10,711 | 1,417,150/37,910 | 78 | 151 | 0 | 76 (55 w/ reasoning) | yes |
| swarm-1789677579 | 1x NVIDIA H200, 143771 MiB | 0 | 565 | warm | 33 | 1 | yes | 2,370,784/10,519 | 1,417,150/37,910 | 70 | 164 | 0 | 68 (50 w/ reasoning) | yes |
| swarm-1789678298 | 1x NVIDIA H200, 143771 MiB | 5 | 1647 | warm | 33 | 1 | yes | 2,039,387/7,340 | 1,417,150/37,910 | 70 | 130 | 0 | 68 (28 w/ reasoning) | yes |
| swarm-1789679031 | 1x NVIDIA H200, 143771 MiB | 5 | 1647 | cold | 33 | 2 | yes | 3,058,137/15,523 | 0/0 | 118 | 200 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789679031 | 1x NVIDIA H200, 143771 MiB | 5 | 1647 | warm | 33 | 3 | yes | 5,624,436/24,791 | 37,374/5,992 | 176 | 370 | 56 | 113 (56 w/ reasoning) | yes |
| swarm-1789680178 | 1x NVIDIA H200, 143771 MiB | 8 | 1816 | cold | 33 | 2 | yes | 5,390,107/20,145 | 0/0 | 162 | 262 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789680178 | 1x NVIDIA H200, 143771 MiB | 8 | 1816 | warm | 33 | 1 | yes | 2,842,745/14,630 | 12,345/2,146 | 83 | 157 | 17 | 81 (36 w/ reasoning) | yes |
| swarm-1789681081 | 1x NVIDIA H200, 143771 MiB | 9 | 1839 | cold | 33 | 3 | yes | 6,341,666/31,941 | 0/0 | 214 | 361 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789681081 | 1x NVIDIA H200, 143771 MiB | 9 | 1839 | warm | 33 | 2 | yes | 3,366,889/16,274 | 25,124/5,029 | 115 | 239 | 42 | 111 (65 w/ reasoning) | yes |
| swarm-1789682217 | 1x NVIDIA H200, 143771 MiB | 11 | 1990 | cold | 33 | 2 | yes | 6,064,334/22,559 | 0/0 | 163 | 304 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789682217 | 1x NVIDIA H200, 143771 MiB | 11 | 1990 | warm | 33 | 1 | yes | 2,501,607/11,173 | 12,601/2,451 | 77 | 139 | 23 | 75 (45 w/ reasoning) | yes |
| swarm-1789683159 | 1x NVIDIA H200, 143771 MiB | 12 | 2214 | cold | 33 | 2 | yes | 5,736,944/29,339 | 0/0 | 156 | 311 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789683159 | 1x NVIDIA H200, 143771 MiB | 12 | 2214 | warm | 33 | 1 | yes | 2,142,376/8,116 | 12,776/2,480 | 72 | 132 | 20 | 70 (38 w/ reasoning) | yes |
| swarm-1789684208 | 1x NVIDIA H200, 143771 MiB | 0 | 565 | cold | 0 | 2 | no | 5,948,153/29,799 | 0/0 | 176 | 671 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789684208 | 1x NVIDIA H200, 143771 MiB | 0 | 565 | warm | 311 | 5 | no | 8,871,113/44,847 | 64,581/23,656 | 300 | 716 | 248 | 287 (156 w/ reasoning) | yes |
| swarm-1789686423 | 1x NVIDIA H200, 143771 MiB | 4 | 3524 | cold | 431 | 4 | no | 5,538,493/35,040 | 0/0 | 193 | 830 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789686423 | 1x NVIDIA H200, 143771 MiB | 4 | 3524 | warm | 310 | 5 | no | 7,855,174/50,152 | 73,575/21,980 | 243 | 708 | 168 | 231 (121 w/ reasoning) | yes |
| swarm-1789688997 | 1x NVIDIA H200, 143771 MiB | 0 | 565 | cold | 440 | 5 | no | 9,960,472/47,695 | 0/0 | 284 | 712 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789688997 | 1x NVIDIA H200, 143771 MiB | 0 | 565 | warm | 445 | 3 | yes | 7,034,795/42,006 | 30,484/29,741 | 188 | 582 | 427 | 182 (119 w/ reasoning) | yes |
| swarm-1789691190 | 1x NVIDIA H200, 143771 MiB | 0 | 565 | cold | 445 | 4 | yes | 8,274,122/39,541 | 0/0 | 274 | 581 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789691190 | 1x NVIDIA H200, 143771 MiB | 0 | 565 | warm | 0 | 5 | no | 5,670,999/51,838 | 68,999/14,639 | 189 | 712 | 153 | 228 (122 w/ reasoning) | yes |
| swarm-1789693180 | 1x NVIDIA H200, 143771 MiB | 5 | 3213 | cold | 436 | 5 | no | 8,991,098/44,213 | 0/0 | 286 | 702 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789693180 | 1x NVIDIA H200, 143771 MiB | 5 | 3213 | warm | 311 | 4 | no | 11,488,435/48,623 | 61,186/16,542 | 313 | 698 | 135 | 305 (195 w/ reasoning) | yes |
| swarm-1789695246 | 1x NVIDIA H200, 143771 MiB | 9 | 4829 | cold | 442 | 5 | no | 9,229,634/40,337 | 0/0 | 287 | 668 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789695246 | 1x NVIDIA H200, 143771 MiB | 9 | 4829 | warm | 445 | 2 | yes | 3,839,497/27,226 | 32,247/9,386 | 115 | 361 | 73 | 111 (75 w/ reasoning) | yes |
| swarm-1789696867 | 1x NVIDIA H200, 143771 MiB | 11 | 5029 | cold | 429 | 5 | no | 9,960,567/45,999 | 0/0 | 279 | 710 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789696867 | 1x NVIDIA H200, 143771 MiB | 11 | 5029 | warm | 0 | 5 | no | 6,820,190/52,976 | 1,417,150/37,910 | 244 | 712 | 0 | 232 (167 w/ reasoning) | yes |
| swarm-1789698823 | 1x NVIDIA H200, 143771 MiB | 11 | 5029 | cold | 0 | 6 | no | 6,504,457/40,387 | 0/0 | 269 | 708 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789698823 | 1x NVIDIA H200, 143771 MiB | 11 | 5029 | warm | 445 | 3 | yes | 5,461,513/30,692 | 1,417,150/37,910 | 163 | 463 | 0 | 164 (118 w/ reasoning) | yes |
| swarm-1789722727 | 1x NVIDIA H200, 143771 MiB | 0 | 565 | cold | 0 | 4 | no | 10,100,025/48,049 | 0/0 | 338 | 664 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789722727 | 1x NVIDIA H200, 143771 MiB | 0 | 565 | warm | 441 | 4 | no | 9,702,575/48,320 | 54,635/11,168 | 281 | 725 | 131 | 273 (208 w/ reasoning) | yes |
| swarm-1789724853 | 1x NVIDIA H200, 143771 MiB | 4 | 3077 | cold | 445 | 3 | yes | 8,799,758/35,742 | 0/0 | 246 | 579 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789724853 | 1x NVIDIA H200, 143771 MiB | 4 | 3077 | warm | 436 | 5 | no | 6,692,277/46,736 | 75,883/19,026 | 253 | 710 | 173 | 241 (169 w/ reasoning) | yes |
| swarm-1789726882 | 1x NVIDIA H200, 143771 MiB | 9 | 4546 | cold | 445 | 4 | yes | 8,790,731/47,242 | 0/0 | 225 | 664 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789726882 | 1x NVIDIA H200, 143771 MiB | 9 | 4546 | warm | 443 | 4 | no | 12,019,187/43,761 | 65,060/20,826 | 313 | 710 | 186 | 305 (206 w/ reasoning) | yes |
| swarm-1789729022 | 1x NVIDIA H200, 143771 MiB | 13 | 6233 | cold | 445 | 3 | yes | 7,511,262/34,221 | 0/0 | 243 | 489 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789729022 | 1x NVIDIA H200, 143771 MiB | 13 | 6233 | warm | 311 | 4 | no | 7,194,381/51,912 | 70,334/24,428 | 224 | 691 | 194 | 220 (160 w/ reasoning) | yes |
| swarm-1789730908 | 1x NVIDIA H200, 143771 MiB | 17 | 6958 | cold | 0 | 5 | no | 7,365,410/48,382 | 0/0 | 272 | 712 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789730908 | 1x NVIDIA H200, 143771 MiB | 17 | 6958 | warm | 445 | 4 | yes | 8,111,380/50,326 | 73,189/26,809 | 236 | 696 | 200 | 229 (154 w/ reasoning) | yes |

| run | gpu | $/hr | run s | GPU $ | skill v | skill tok | arm | passed | attempts | converged | attempt tok (in/out) | distil tok (in/out) | turns | attempt s | distil s | steps | counts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| swarm-1789755824 | 1x NVIDIA H200 | 4.59 | 1408 | 1.79 | 14 | 1688 | cold | 445 | 4 | yes | 11,671,399/44,582 | 0/0 | 321 | 703 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789755824 | 1x NVIDIA H200 | 4.59 | 1408 | 1.79 | 14 | 1688 | warm | 445 | 4 | yes | 5,627,667/18,596 | 0/0 | 185 | 532 | 168 | 177 (0 w/ reasoning) | yes |
| swarm-1789758056 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1049 | 1.34 | 16 | 1688 | cold | 0 | 4 | no | 6,242,939/45,834 | 0/0 | 209 | 668 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789758056 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1049 | 1.34 | 16 | 1688 | warm | 0 | 4 | no | 6,424,966/39,625 | 1,234,580/28,916 | 199 | 709 | 108 | 188 (0 w/ reasoning) | yes |
| swarm-1789759727 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1181 | 1.51 | 20 | 1447 | cold | 0 | 5 | no | 5,247,546/34,931 | 0/0 | 201 | 674 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789759727 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1181 | 1.51 | 20 | 1447 | warm | 346 | 4 | no | 6,988,492/38,713 | 1,730,453/42,648 | 205 | 719 | 129 | 195 (0 w/ reasoning) | yes |
| swarm-1789769262 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1184 | 1.51 | 24 | 1828 | cold | 311 | 4 | no | 6,842,037/48,500 | 0/0 | 229 | 703 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789769262 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1184 | 1.51 | 24 | 1828 | warm | 311 | 4 | no | 7,780,766/42,168 | 111,880/25,303 | 213 | 699 | 287 | 204 (0 w/ reasoning) | yes |
| swarm-1789771004 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1255 | 1.60 | 28 | 8704 | cold | 310 | 5 | no | 5,523,139/33,335 | 0/0 | 203 | 677 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789771004 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1255 | 1.60 | 28 | 8704 | warm | 310 | 4 | no | 9,813,817/41,539 | 130,043/33,380 | 233 | 690 | 309 | 222 (0 w/ reasoning) | yes |
| swarm-1789773045 | 1x NVIDIA H200 | 4.59 | 1319 | 1.68 | 32 | 9429 | cold | 0 | 4 | no | 6,849,352/43,881 | 0/0 | 243 | 689 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789773045 | 1x NVIDIA H200 | 4.59 | 1319 | 1.68 | 32 | 9429 | warm | 0 | 5 | no | 5,888,999/35,165 | 0/0 | 192 | 688 | 372 | 178 (0 w/ reasoning) | yes |
| swarm-1789773045 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1319 | 1.68 | 32 | 9429 | cold | 0 | 4 | no | 6,849,352/43,881 | 0/0 | 243 | 689 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789773045 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1319 | 1.68 | 32 | 9429 | warm | 0 | 5 | no | 5,888,999/35,165 | 160,670/43,945 | 192 | 688 | 372 | 178 (0 w/ reasoning) | yes |
| swarm-1789774687 | 1x NVIDIA H200, 143771 MiB | 4.59 | 909 | 1.16 | 37 | 11404 | cold | 445 | 2 | yes | 6,127,546/23,653 | 0/0 | 175 | 367 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789774687 | 1x NVIDIA H200, 143771 MiB | 4.59 | 909 | 1.16 | 37 | 11404 | warm | 445 | 3 | yes | 6,652,382/23,975 | 100,890/29,650 | 153 | 472 | 245 | 146 (0 w/ reasoning) | yes |
| swarm-1789776082 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1264 | 1.61 | 40 | 12051 | cold | 311 | 2 | no | 5,672,761/24,868 | 0/0 | 153 | 708 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789776082 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1264 | 1.61 | 40 | 12051 | warm | 311 | 2 | no | 5,623,601/21,948 | 67,457/20,585 | 136 | 684 | 156 | 129 (0 w/ reasoning) | yes |
| swarm-1789777832 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1170 | 1.49 | 42 | 12471 | cold | 0 | 3 | no | 3,751,330/31,870 | 0/0 | 122 | 493 | 0 | 0 (0 w/ reasoning) | yes |
| swarm-1789777832 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1170 | 1.49 | 42 | 12471 | warm | 310 | 3 | no | 3,903,979/19,897 | 102,901/31,278 | 117 | 417 | 166 | 108 (0 w/ reasoning) | yes |
| swarm-1789810092 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1562 | 1.99 | 45 | 12634 | cold | 436 | 4 | no | 11,239,437/48,140 | 0/0 | 299 | 722 | 0 | 0 (reasoning UNCOUNTED) | yes |
| swarm-1789810092 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1562 | 1.99 | 45 | 12634 | warm | 310 | 4 | no | 6,795,671/44,221 | 154,078/60,785 | 189 | 721 | 646 | 185 (183 w/ reasoning) | yes |
| swarm-1789812476 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1564 | 1.99 | 0 | 569 | cold | 0 | 4 | no | 7,168,298/49,304 | 0/0 | 237 | 721 | 0 | 0 (reasoning UNCOUNTED) | yes |
| swarm-1789812476 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1564 | 1.99 | 0 | 569 | warm | 310 | 4 | no | 5,143,024/33,993 | 133,605/60,103 | 170 | 690 | 717 | 159 (159 w/ reasoning) | yes |
| swarm-1789847857 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1886 | 2.40 | 0 | 569 | cold | 310 | 5 | no | 9,103,934/41,770 | 0/0 | 287 | 714 | 0 | 0 (reasoning UNCOUNTED) | yes |
| swarm-1789847857 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1886 | 2.40 | 0 | 569 | warm | 310 | 5 | no | 6,111,871/33,915 | 194,008/70,800 | 194 | 675 | 872 | 184 (179 w/ reasoning) | yes |
| swarm-1789849748 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1216 | 1.55 | 10 | 3018 | cold | 445 | 3 | yes | 7,679,618/29,853 | 0/0 | 215 | 645 | 0 | 0 (reasoning UNCOUNTED) | yes |
| swarm-1789849748 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1216 | 1.55 | 10 | 3018 | warm | 445 | 2 | yes | 6,274,463/25,728 | 115,724/22,843 | 150 | 648 | 288 | 144 (144 w/ reasoning) | yes |
| swarm-1789850978 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1158 | 1.48 | 14 | 5047 | cold | 0 | 3 | no | 7,383,776/36,171 | 0/0 | 218 | 663 | 0 | 0 (reasoning UNCOUNTED) | yes |
| swarm-1789850978 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1158 | 1.48 | 14 | 5047 | warm | 445 | 2 | yes | 4,586,642/18,756 | 148,748/23,113 | 124 | 479 | 275 | 120 (119 w/ reasoning) | yes |
| swarm-1789852145 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1350 | 1.72 | 18 | 2594 | cold | 311 | 3 | no | 9,974,557/45,489 | 0/0 | 262 | 740 | 0 | 0 (reasoning UNCOUNTED) | yes |
| swarm-1789852145 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1350 | 1.72 | 18 | 2594 | warm | 0 | 3 | no | 7,399,323/36,871 | 288,967/36,445 | 206 | 776 | 405 | 198 (199 w/ reasoning) | yes |
| swarm-1789853501 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1607 | 2.05 | 24 | 2869 | cold | 440 | 5 | no | 8,934,914/34,653 | 0/0 | 273 | 733 | 0 | 0 (reasoning UNCOUNTED) | yes |
| swarm-1789853501 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1607 | 2.05 | 24 | 2869 | warm | 310 | 5 | no | 8,083,934/32,057 | 619,441/68,628 | 221 | 715 | 652 | 209 (207 w/ reasoning) | yes |
| swarm-1789855113 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1119 | 1.43 | 34 | 3997 | cold | 0 | 4 | no | 10,108,757/41,309 | 0/0 | 291 | 678 | 0 | 0 (reasoning UNCOUNTED) | yes |
| swarm-1789855113 | 1x NVIDIA H200, 143771 MiB | 4.59 | 1119 | 1.43 | 34 | 3997 | warm | 311 | 3 | no | 6,622,360/34,461 | 293,976/30,575 | 175 | 569 | 276 | 85 (170 w/ reasoning) | yes |
