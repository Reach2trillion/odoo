/* ==========================================================================
   ABJ Shop — catalogue data
   Every customer-facing string carries an `en` and a `km` variant.
   Edit this file to change products; no build step is required.
   ========================================================================== */

const SHOP = {
  currency: { code: 'USD', symbol: '$', rielRate: 4100 },

  contact: {
    phone: '+855 12 345 678',
    telegram: 'https://t.me/abjshop',
    messenger: 'https://m.me/abjshop',
    facebook: 'https://facebook.com/abjshop',
    tiktok: 'https://tiktok.com/@abjshop',
    instagram: 'https://instagram.com/abjshop',
    email: 'hello@abj.shop',
    address: {
      en: 'St. 271, Sangkat Toul Tumpoung, Phnom Penh',
      km: 'ផ្លូវ ២៧១ សង្កាត់ទួលទំពូង រាជធានីភ្នំពេញ'
    },
    hours: { en: 'Every day · 8:00 AM – 8:00 PM', km: 'រៀងរាល់ថ្ងៃ · ម៉ោង ៨ ព្រឹក – ៨ យប់' }
  },

  categories: [
    { slug: 'skincare', img: 'cat-skincare.svg',
      name: { en: 'Skincare', km: 'ថែរក្សាស្បែក' },
      tagline: { en: 'Serums, creams & sunscreen', km: 'សេរ៉ូម ក្រែម និងក្រែមការពារកម្តៅ' } },
    { slug: 'cosmetic', img: 'cat-cosmetic.svg',
      name: { en: 'Cosmetic', km: 'គ្រឿងសម្អាង' },
      tagline: { en: 'Lips, cheeks & complexion', km: 'បបូរមាត់ ថ្ពាល់ និងមុខ' } },
    { slug: 'bodycare', img: 'cat-bodycare.svg',
      name: { en: 'Body Care', km: 'ថែរក្សាខ្លួន' },
      tagline: { en: 'Lotion, scrub & smoothing', km: 'ឡេលាបខ្លួន ស្គ្រាប និងបំភ្លឺ' } },
    { slug: 'haircare', img: 'cat-haircare.svg',
      name: { en: 'Hair Care', km: 'ថែរក្សាសក់' },
      tagline: { en: 'Repair & shine', km: 'ជួសជុល និងបំភ្លឺសក់' } }
  ],

  products: [
    {
      slug: 'sunscreen-daily-shield', category: 'skincare', price: 12.5, oldPrice: 15,
      badge: 'best', rating: 4.9, reviews: 428, sizes: ['50ml'],
      name: { en: 'Daily Shield Sunscreen SPF50+ PA++++', km: 'ក្រែមការពារកម្តៅថ្ងៃ SPF50+ PA++++' },
      short: { en: 'Weightless, no white cast, built for Cambodian sun.', km: 'ស្រាល មិនស ស័ក្តិសមនឹងកម្តៅថ្ងៃនៅកម្ពុជា។' },
      desc: {
        en: 'A featherlight daily sunscreen that absorbs in seconds and leaves zero white cast. Broad-spectrum SPF50+ PA++++ protection shields against UVA, UVB and visible light while niacinamide keeps tone even through the hottest hours of the day.',
        km: 'ក្រែមការពារកម្តៅថ្ងៃដ៏ស្រាល ជ្រាបចូលស្បែកយ៉ាងលឿន និងមិនបន្សល់ស្នាមសឡើយ។ ការពារពីកាំរស្មី UVA UVB និងពន្លឺមើលឃើញ ជាមួយនឹង Niacinamide ដែលជួយឲ្យសម្បុរស្បែកស្មើគ្នា។'
      },
      howto: {
        en: 'Apply two finger-lengths as the last step of your morning routine. Reapply every 3–4 hours outdoors.',
        km: 'លាបប្រវែងពីរម្រាមដៃ ជាជំហានចុងក្រោយនៃការថែរក្សាពេលព្រឹក។ លាបឡើងវិញរៀងរាល់ ៣–៤ ម៉ោង នៅពេលនៅខាងក្រៅ។'
      },
      ingredients: {
        en: 'Aqua, Ethylhexyl Methoxycinnamate, Niacinamide 4%, Centella Asiatica Extract, Panthenol, Glycerin, Tocopherol.',
        km: 'ទឹក, Ethylhexyl Methoxycinnamate, Niacinamide ៤%, សារធាតុចម្រាញ់ពីត្រកួន, Panthenol, Glycerin, វីតាមីន E។'
      }
    },
    {
      slug: 'vitamin-c-serum', category: 'skincare', price: 18, oldPrice: null,
      badge: 'best', rating: 4.8, reviews: 316, sizes: ['30ml'],
      name: { en: 'Glow Vitamin C Serum 15%', km: 'សេរ៉ូមវីតាមីន C ១៥% បំភ្លឺស្បែក' },
      short: { en: 'Fades dark spots and wakes up dull skin.', km: 'បន្ថយអាចម៍រុយ និងធ្វើឲ្យស្បែកភ្លឺរស់រវើក។' },
      desc: {
        en: 'A stabilised 15% vitamin C serum paired with ferulic acid and vitamin E. Used nightly it visibly softens dark spots left by sun and acne, and gives tired skin back its glow in about four weeks.',
        km: 'សេរ៉ូមវីតាមីន C ១៥% រួមផ្សំជាមួយ Ferulic Acid និងវីតាមីន E។ ប្រើរៀងរាល់យប់ អាចជួយបន្ថយស្នាមខ្មៅដែលបណ្តាលមកពីកម្តៅថ្ងៃ និងមុន ព្រមទាំងធ្វើឲ្យស្បែកភ្លឺឡើងវិញក្នុងរយៈពេលប្រហែល ៤ សប្តាហ៍។'
      },
      howto: {
        en: 'After cleansing and toner, press 3–4 drops over face and neck. Follow with moisturiser. Always wear sunscreen the next morning.',
        km: 'បន្ទាប់ពីលាងមុខ និងទឹកតូនិច ចាក់ ៣–៤ តំណក់ លាបលើមុខ និងក។ បន្ទាប់មកលាបក្រែមផ្តល់សំណើម។ ត្រូវលាបក្រែមការពារកម្តៅនៅពេលព្រឹកជានិច្ច។'
      },
      ingredients: {
        en: 'Aqua, Ascorbic Acid 15%, Ferulic Acid, Tocopherol, Hyaluronic Acid, Propanediol.',
        km: 'ទឹក, Ascorbic Acid ១៥%, Ferulic Acid, វីតាមីន E, Hyaluronic Acid, Propanediol។'
      }
    },
    {
      slug: 'night-repair-cream', category: 'skincare', price: 16, oldPrice: 20,
      badge: 'sale', rating: 4.7, reviews: 188, sizes: ['50g'],
      name: { en: 'Night Repair Cream', km: 'ក្រែមថែរក្សាស្បែកពេលយប់' },
      short: { en: 'Rich overnight repair with 3% peptides.', km: 'ថែរក្សាស្បែកពេញមួយយប់ ជាមួយ Peptide ៣%។' },
      desc: {
        en: 'A cushiony night cream with peptides, squalane and ceramides that rebuilds the skin barrier while you sleep. Wake up to skin that feels bouncy rather than tight — even after a long day in air conditioning.',
        km: 'ក្រែមពេលយប់ដ៏ទន់រលោង ផ្សំដោយ Peptide, Squalane និង Ceramide ដែលជួយស្តារស្រទាប់ការពារស្បែកនៅពេលអ្នកដេក។ ភ្ញាក់ឡើងស្បែកមានសំណើម មិនរឹងតឹង។'
      },
      howto: { en: 'Warm a pearl-size amount and press into clean skin as the last night-time step.', km: 'យកបរិមាណប៉ុនគ្រាប់ផ្កាយ លាបលើស្បែកស្អាត ជាជំហានចុងក្រោយពេលយប់។' },
      ingredients: { en: 'Aqua, Squalane, Ceramide NP, Palmitoyl Tripeptide-1, Shea Butter, Glycerin.', km: 'ទឹក, Squalane, Ceramide NP, Palmitoyl Tripeptide-1, ខ្លាញ់ Shea, Glycerin។' }
    },
    {
      slug: 'rose-water-toner', category: 'skincare', price: 9.5, oldPrice: null,
      badge: null, rating: 4.6, reviews: 142, sizes: ['150ml', '300ml'],
      name: { en: 'Rose Water Hydrating Toner', km: 'ទឹកតូនិចផ្កាកុលាបផ្តល់សំណើម' },
      short: { en: 'Alcohol-free calm for hot, tired skin.', km: 'គ្មានជាតិអាល់កុល ជួយបន្ថូរបន្ថយស្បែកក្តៅ។' },
      desc: {
        en: 'Steam-distilled rose water with panthenol and 5% glycerin. It cools skin down after a day on the moto and preps it so serums absorb better.',
        km: 'ទឹកផ្កាកុលាបចម្រាញ់ដោយចំហាយ រួមជាមួយ Panthenol និង Glycerin ៥%។ ជួយបន្ថយកម្តៅស្បែកបន្ទាប់ពីធ្វើដំណើរពេញមួយថ្ងៃ និងរៀបចំស្បែកឲ្យទទួលសេរ៉ូមបានល្អ។'
      },
      howto: { en: 'Sweep over face with a cotton pad, or spritz any time skin feels hot.', km: 'ជូតលើមុខដោយសំឡីទន់ ឬបាញ់នៅពេលស្បែកមានអារម្មណ៍ក្តៅ។' },
      ingredients: { en: 'Rosa Damascena Flower Water, Glycerin 5%, Panthenol, Allantoin.', km: 'ទឹកផ្កាកុលាប, Glycerin ៥%, Panthenol, Allantoin។' }
    },
    {
      slug: 'gentle-foam-cleanser', category: 'skincare', price: 8.5, oldPrice: null,
      badge: 'new', rating: 4.7, reviews: 96, sizes: ['120ml'],
      name: { en: 'Gentle Foam Cleanser pH 5.5', km: 'សាប៊ូលាងមុខពពុះទន់ភ្លន់ pH 5.5' },
      short: { en: 'Removes sunscreen without stripping.', km: 'លាងក្រែមការពារកម្តៅបានស្អាត ដោយមិនធ្វើឲ្យស្បែកស្ងួត។' },
      desc: {
        en: 'A soft amino-acid foam that dissolves sunscreen, sweat and city dust in one wash, and leaves skin comfortable instead of squeaky.',
        km: 'ពពុះទន់ភ្លន់ដែលមានផ្សំពី Amino Acid អាចលាងសម្អាតក្រែមការពារកម្តៅ ញើស និងធូលីបាននៅក្នុងការលាងតែម្តង ដោយទុកឲ្យស្បែកមានអារម្មណ៍ស្រួល។'
      },
      howto: { en: 'Massage over damp skin morning and night, rinse with cool water.', km: 'ម៉ាស្សាលើស្បែកសើមពេលព្រឹក និងពេលយប់ រួចលាងចេញដោយទឹកត្រជាក់។' },
      ingredients: { en: 'Aqua, Sodium Cocoyl Glycinate, Glycerin, Centella Asiatica, Panthenol.', km: 'ទឹក, Sodium Cocoyl Glycinate, Glycerin, ត្រកួន, Panthenol។' }
    },
    {
      slug: 'silk-body-lotion', category: 'bodycare', price: 11, oldPrice: 14,
      badge: 'sale', rating: 4.8, reviews: 233, sizes: ['250ml', '400ml'],
      name: { en: 'Silk Body Lotion', km: 'ឡេលាបខ្លួនទន់រលោង' },
      short: { en: 'Non-sticky glow in Phnom Penh humidity.', km: 'មិនស្អិត ភ្លឺរលោង សូម្បីនៅពេលអាកាសធាតុសើម។' },
      desc: {
        en: 'A light milk with niacinamide and rice bran oil that sinks in fast — no sticky film under clothes, just soft skin with a natural sheen.',
        km: 'ឡេស្រាលផ្សំដោយ Niacinamide និងប្រេងកន្ទក់អង្ករ ដែលជ្រាបចូលលឿន មិនស្អិតនៅពេលពាក់សម្លៀកបំពាក់ ធ្វើឲ្យស្បែកទន់ភ្លឺ។'
      },
      howto: { en: 'Smooth over the whole body after showering, while skin is still slightly damp.', km: 'លាបលើខ្លួនទាំងមូលបន្ទាប់ពីងូតទឹក ខណៈស្បែកនៅសើមបន្តិច។' },
      ingredients: { en: 'Aqua, Niacinamide 3%, Oryza Sativa Bran Oil, Glycerin, Shea Butter.', km: 'ទឹក, Niacinamide ៣%, ប្រេងកន្ទក់អង្ករ, Glycerin, ខ្លាញ់ Shea។' }
    },
    {
      slug: 'underarm-brightening', category: 'bodycare', price: 10, oldPrice: null,
      badge: 'best', rating: 4.6, reviews: 274, sizes: ['30g'],
      name: { en: 'Underarm Brightening Cream', km: 'ក្រែមបំភ្លឺក្លៀក' },
      short: { en: 'For dark underarms, knees and elbows.', km: 'សម្រាប់ក្លៀក ជង្គង់ និងកែងដៃខ្មៅ។' },
      desc: {
        en: 'Alpha-arbutin and licorice root gently lift discolouration caused by shaving and friction. Fragrance-free and safe to use daily.',
        km: 'Alpha-Arbutin និងឫសមើមឈូក ជួយបន្ថយភាពខ្មៅដែលបណ្តាលមកពីការកោរ និងការកកិត។ គ្មានក្លិន និងអាចប្រើប្រចាំថ្ងៃបាន។'
      },
      howto: { en: 'Apply a thin layer to clean, dry skin at night. Do not use immediately after shaving.', km: 'លាបស្តើងៗលើស្បែកស្អាត និងស្ងួតនៅពេលយប់។ កុំប្រើភ្លាមបន្ទាប់ពីកោរ។' },
      ingredients: { en: 'Aqua, Alpha-Arbutin 2%, Glycyrrhiza Glabra Root Extract, Niacinamide, Allantoin.', km: 'ទឹក, Alpha-Arbutin ២%, សារធាតុចម្រាញ់ឫសមើមឈូក, Niacinamide, Allantoin។' }
    },
    {
      slug: 'coffee-body-scrub', category: 'bodycare', price: 7.5, oldPrice: null,
      badge: null, rating: 4.5, reviews: 118, sizes: ['200g'],
      name: { en: 'Coffee Body Scrub', km: 'ស្គ្រាបខាត់ខ្លួនកាហ្វេ' },
      short: { en: 'Cambodian robusta grounds + coconut oil.', km: 'កាហ្វេរ៉ូបូស្តាខ្មែរ ផ្សំប្រេងដូង។' },
      desc: {
        en: 'Locally sourced robusta grounds blended with virgin coconut oil and sea salt to buff away rough patches and leave skin smelling like a morning café.',
        km: 'កាហ្វេរ៉ូបូស្តាក្នុងស្រុក លាយជាមួយប្រេងដូងសុទ្ធ និងអំបិលសមុទ្រ ជួយខាត់សម្អាតស្បែករដុប និងបន្សល់ក្លិនក្រអូបដូចកាហ្វេពេលព្រឹក។'
      },
      howto: { en: 'Massage onto wet skin twice a week in circular motions, then rinse.', km: 'ម៉ាស្សាលើស្បែកសើមពីរដងក្នុងមួយសប្តាហ៍ ជារង្វង់ រួចលាងចេញ។' },
      ingredients: { en: 'Coffea Robusta Powder, Cocos Nucifera Oil, Maris Sal, Tocopherol.', km: 'ម្សៅកាហ្វេរ៉ូបូស្តា, ប្រេងដូង, អំបិលសមុទ្រ, វីតាមីន E។' }
    },
    {
      slug: 'silky-hair-serum', category: 'haircare', price: 13, oldPrice: null,
      badge: 'new', rating: 4.7, reviews: 87, sizes: ['60ml'],
      name: { en: 'Silky Hair Repair Serum', km: 'សេរ៉ូមថែសក់ឲ្យរលោង' },
      short: { en: 'Tames frizz and split ends in one week.', km: 'ជួយបន្ថយសក់រញ៉េរញ៉ៃ និងសក់បែកចុងក្នុងមួយសប្តាហ៍។' },
      desc: {
        en: 'Argan and camellia oils with hydrolysed keratin seal split ends and cut down drying time, without weighing hair flat.',
        km: 'ប្រេង Argan និង Camellia រួមជាមួយ Keratin ជួយបិទចុងសក់បែក និងបន្ថយពេលសម្ងួតសក់ ដោយមិនធ្វើឲ្យសក់ធ្ងន់។'
      },
      howto: { en: 'Warm 2–3 drops in the palms and run through damp mid-lengths and ends.', km: 'យក ២–៣ តំណក់ដាក់លើបាតដៃ រួចលាបលើសក់សើមចាប់ពីកណ្តាលដល់ចុង។' },
      ingredients: { en: 'Argania Spinosa Kernel Oil, Camellia Oil, Hydrolyzed Keratin, Cyclopentasiloxane.', km: 'ប្រេង Argan, ប្រេង Camellia, Hydrolyzed Keratin, Cyclopentasiloxane។' }
    },
    {
      slug: 'velvet-lip-tint', category: 'cosmetic', price: 6.5, oldPrice: 8,
      badge: 'sale', rating: 4.9, reviews: 512, sizes: ['#01 Rose', '#02 Coral', '#03 Plum'],
      name: { en: 'Velvet Lip Tint', km: 'ទឹកលាបបបូរមាត់ Velvet' },
      short: { en: 'All-day colour that survives iced coffee.', km: 'ពណ៌ជាប់បានពេញមួយថ្ងៃ ទោះផឹកកាហ្វេទឹកកក។' },
      desc: {
        en: 'A weightless velvet tint that sets in seconds and stays put through meals. Buildable from a soft everyday wash to a full bold lip.',
        km: 'ទឹកលាបបបូរមាត់ស្រាល ស្ងួតលឿន និងជាប់បានយូរទោះបរិភោគអាហារ។ អាចលាបស្តើងសម្រាប់ប្រចាំថ្ងៃ ឬលាបក្រាស់សម្រាប់រាត្រី។'
      },
      howto: { en: 'Apply from the centre of the lips outward. Layer for a deeper shade.', km: 'លាបចាប់ពីកណ្តាលបបូរមាត់ទៅក្រៅ។ លាបច្រើនជាន់ដើម្បីបានពណ៌ចាស់។' },
      ingredients: { en: 'Isododecane, Dimethicone, Silica, CI 15850, Tocopherol.', km: 'Isododecane, Dimethicone, Silica, CI 15850, វីតាមីន E។' }
    },
    {
      slug: 'petal-blush', category: 'cosmetic', price: 6, oldPrice: null,
      badge: 'best', rating: 4.8, reviews: 604, sizes: ['#01 Peach', '#02 Rose', '#03 Berry'],
      name: { en: 'Petal Blush', km: 'ថ្នាំលាបថ្ពាល់ Petal' },
      short: { en: 'Silky powder, natural flush, no patchiness.', km: 'ម្សៅរលោង ពណ៌ធម្មជាតិ មិនប្រឡាក់។' },
      desc: {
        en: 'A finely milled blush that blends in one sweep and holds its colour through a humid afternoon. Three shades made for warm Khmer skin tones.',
        km: 'ថ្នាំលាបថ្ពាល់ម្សៅល្អិត លាបងាយ និងជាប់បានយូរទោះអាកាសធាតុសើម។ មានបីពណ៌ ដែលរចនាឡើងសម្រាប់សម្បុរស្បែកខ្មែរ។'
      },
      howto: { en: 'Sweep onto the apples of the cheeks and blend upward toward the temple.', km: 'លាបលើថ្ពាល់ រួចលាបឡើងលើឆ្ពោះទៅត្រចៀក។' },
      ingredients: { en: 'Talc, Mica, Zinc Stearate, Dimethicone, CI 77491.', km: 'Talc, Mica, Zinc Stearate, Dimethicone, CI 77491។' }
    },
    {
      slug: 'glow-cushion', category: 'cosmetic', price: 15, oldPrice: null,
      badge: null, rating: 4.6, reviews: 209, sizes: ['#21 Light', '#23 Natural', '#25 Warm'],
      name: { en: 'Glow Cushion Foundation SPF35', km: 'ខ្វិចសិនម្សៅមុខ Glow SPF35' },
      short: { en: 'Dewy medium coverage with sun filter.', km: 'បិទបាំងល្មម ភ្លឺរលោង មានការពារកម្តៅ។' },
      desc: {
        en: 'A cushion that evens out tone without the cakey finish, plus SPF35 for the ride to work. Comes with a refill sponge.',
        km: 'ខ្វិចសិនដែលធ្វើឲ្យសម្បុរស្បែកស្មើគ្នា ដោយមិនក្រាស់ពេក ព្រមទាំងមាន SPF35 សម្រាប់ការធ្វើដំណើរ។ មានផ្តល់ស្ពុងជូនផងដែរ។'
      },
      howto: { en: 'Press — never swipe — from the centre of the face outward.', km: 'ចុចថ្នមៗ ចាប់ពីកណ្តាលមុខទៅក្រៅ (កុំជូត)។' },
      ingredients: { en: 'Aqua, Titanium Dioxide, Cyclopentasiloxane, Niacinamide, Glycerin.', km: 'ទឹក, Titanium Dioxide, Cyclopentasiloxane, Niacinamide, Glycerin។' }
    }
  ],

  reviews: [
    { name: 'Sreymom C.', city: { en: 'Phnom Penh', km: 'ភ្នំពេញ' },
      text: { en: 'The sunscreen is the only one I have found that does not turn grey on my skin. I bought three more for my sisters.',
              km: 'ក្រែមការពារកម្តៅនេះ គឺជាមួយគត់ដែលមិនធ្វើឲ្យស្បែកខ្ញុំប្រែជាពណ៌ប្រផេះ។ ខ្ញុំបានទិញបីទៀតសម្រាប់បងប្អូនស្រី។' } },
    { name: 'Dara S.', city: { en: 'Siem Reap', km: 'សៀមរាប' },
      text: { en: 'Ordered at 9pm, delivered to Siem Reap in two days. The vitamin C serum really did fade my acne marks.',
              km: 'កម្មង់នៅម៉ោង ៩ យប់ ដឹកជញ្ជូនដល់សៀមរាបក្នុងរយៈពេលពីរថ្ងៃ។ សេរ៉ូមវីតាមីន C ពិតជាបន្ថយស្នាមមុនរបស់ខ្ញុំមែន។' } },
    { name: 'Chanthy L.', city: { en: 'Battambang', km: 'បាត់ដំបង' },
      text: { en: 'The lip tint stays on all day at the market. Good price, and the team answers on Telegram straight away.',
              km: 'ទឹកលាបបបូរមាត់ជាប់បានពេញមួយថ្ងៃនៅផ្សារ។ តម្លៃសមរម្យ ហើយក្រុមការងារឆ្លើយតបតាម Telegram លឿនណាស់។' } }
  ]
};

/* ---------------------------------------------------------------- helpers */
const findProduct = (slug) => SHOP.products.find((p) => p.slug === slug);
const productImage = (p, alt) => `assets/img/p-${p.slug}${alt ? '-b' : ''}.svg`;
const money = (v) => `${SHOP.currency.symbol}${v.toFixed(2)}`;
const riel = (v) => `${Math.round((v * SHOP.currency.rielRate) / 100) * 100}៛`;
