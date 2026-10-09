# Eval results (2026-10-09 20:07)

- Model: `qwen3:1.7b` via Ollama, `num_thread=4`, CPU only. Mall: `mall.json`. Mode: rules first, then LLM.
- Messages: 50. Handled by rules: 43. LLM fallbacks: 0.
- Intent accuracy: 98% (49/50)
- Category F1 (find/plan): 0.94
- Edit ops exact: 100% (12/12)
- Landmarks found: 100% (8/8)
- Latency all messages: median 0.3 ms, p95 260 ms
- Latency LLM calls: median 259.9 ms, p95 318 ms

| ok | source | message | intent | detail |
|---|---|---|---|---|
| ✓ | rules | papaayos ko screen ng phone ko, kakain, tapos bibili ng regalo kay mama | plan | cats ['food', 'gift', 'phone_repair'] f1=1.00 |
| ✓ | rules | sira cellfone ko tapos gutom na ko | plan | cats ['food', 'phone_repair'] f1=1.00 |
| ✓ | rules | need ko magpa-repair ng sapatos and bumili ng damit | plan | cats ['clothing', 'shoe_repair'] f1=1.00 |
| ✓ | rules | withdraw muna ako sa atm then kape | plan | cats ['atm', 'cafe'] f1=1.00 |
| ✓ | rules | bibili ako ng gamot tapos grocery | plan | cats ['grocery', 'pharmacy'] f1=1.00 |
| ✓ | rules | I need to fix my phone battery, grab lunch, and buy new shoes | plan | cats ['food', 'phone_repair', 'shoes'] f1=1.00 |
| ✓ | rules | magpapadala ng pera, tapos kakain ng ramen | plan | cats ['food', 'remittance'] f1=1.00 |
| ✓ | llm | cr muna tapos milk tea | plan | cats ['cafe', 'food'] f1=0.50 |
| ✓ | llm | ipaayos yung basag na screen, bili ng charger, tapos merienda | plan | cats ['electronics', 'food', 'phone_repair'] f1=1.00 |
| ✓ | rules | hanap ako ng pasalubong at kape | plan | cats ['cafe', 'gift'] f1=1.00 |
| ✓ | llm | gusto ko kumain ng sizzling tapos bumili ng relo | plan | cats ['food', 'gift'] f1=0.50 |
| ✓ | llm | papalitan ko battery ng phone, tapos titingin ng laptop | plan | cats ['electronics', 'phone_repair'] f1=1.00 |
| ✓ | llm | deposit sa bdo then grocery shopping | plan | cats ['grocery', 'remittance'] f1=0.50 |
| ✓ | rules | kain tayo then laro sa arcade or games | plan | cats ['food', 'gaming'] f1=1.00 |
| ✓ | rules | bili ng notebook at ballpen tapos kape | plan | cats ['books_stationery', 'cafe'] f1=1.00 |
| ✓ | rules | skincare tapos damit pang-office | plan | cats ['beauty', 'clothing'] f1=1.00 |
| ✓ | rules | phone repair, food, gift | plan | cats ['food', 'gift', 'phone_repair'] f1=1.00 |
| ✓ | rules | ayusin ang sira kong takong ng sapatos tapos kain | plan | cats ['food', 'shoe_repair'] f1=1.00 |
| ✓ | llm | lunch muna bago mag-shopping ng damit | plan | cats ['clothing', 'food'] f1=1.00 |
| ✓ | rules | kailangan ko ng gamot sa ubo at pagkain | plan | cats ['food', 'pharmacy'] f1=1.00 |
| ✓ | rules | sabi ng technician 30 mins lang | edit | ops ['set_duration'] ok |
| ✓ | rules | sabi ng technician 1 oras daw, tapos kailangan ko umalis ng 5 | edit | ops ['deadline', 'set_duration'] ok |
| ✓ | rules | ready daw by 4pm | edit | ops ['set_ready_at'] ok |
| ✓ | rules | gutom na ko, kain muna | edit | ops ['order'] ok |
| ✓ | rules | wag na yung damit | edit | ops ['remove'] ok |
| ✓ | rules | naiwan ko na yung phone sa repair | edit | ops ['status'] ok |
| ✓ | rules | may kasama akong naka-wheelchair | edit | ops ['elevator_only'] ok |
| ✓ | rules | dagdag mo yung pharmacy | edit | ops ['add'] ok |
| ✓ | llm | the guy said it will take two hours | edit | ops ['set_duration'] ok |
| ✓ | rules | uuwi na ako ng 6 so bilisan natin | edit | ops ['deadline'] ok |
| ✓ | rules | nakuha ko na yung phone | edit | ops ['status'] ok |
| ✓ | rules | pasama na rin ng ATM | edit | ops ['add'] ok |
| ✓ | rules | nasa tabi ako ng Starbucks, katapat ng H&M | locate | landmarks ['h&m', 'starbucks'] ok |
| ✓ | rules | andito ako sa harap ng Uniqlo | locate | landmarks ['uniqlo'] ok |
| ✓ | rules | kita ko yung Goldilocks tsaka Mary Grace | locate | landmarks ['goldilocks', 'mary grace cafe'] ok |
| ✓ | rules | I'm near ASUS and Techno on the 4th floor | locate | landmarks ['asus concept store', 'techno'] ok |
| ✓ | rules | sabi ni ate nasa tapat daw siya ng Kultura | locate | landmarks ['kultura filipino'] ok |
| ✓ | rules | nandito ako malapit sa La Botica at BDO | locate | landmarks ['bdo', 'la botica'] ok |
| ✓ | rules | nasa may escalator ako, kita ko Miniso | locate | landmarks ['miniso'] ok |
| ✓ | rules | beside Fuel Burgers, across Gong Cha | locate | landmarks ['fuel burgers', 'gong cha'] ok |
| ✓ | rules | saan ang CR | find | cats ['restroom'] f1=1.00 |
| ✓ | rules | may atm ba dito | find | cats ['atm'] f1=1.00 |
| ✓ | rules | where can I fix my cracked phone screen | find | cats ['phone_repair'] f1=1.00 |
| ✓ | rules | saan pwede magpaayos ng sapatos | find | cats ['shoe_repair'] f1=1.00 |
| ✓ | rules | botika | find | cats ['pharmacy'] f1=1.00 |
| ✓ | rules | gusto ko ng milk tea | find | cats ['food'] f1=1.00 |
| ✓ | rules | salamat po! | other |  |
| ✓ | rules | hello | other |  |
| ✓ | rules | anong oras kayo nagsasara | other |  |
| ✗ | rules | ang init dito grabe | find |  |
