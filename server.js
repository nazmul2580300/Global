const express = require('express');
const mongoose = require('mongoose');
const cron = require('node-cron');

const app = express();
app.use(express.json()); // JSON ডাটা পড়ার জন্য
app.get('/', (req, res) => {
    res.send('স্বাগতম! আপনার ইনভেস্টিং সাইটের সার্ভার একদম ঠিকঠাক চলছে।');
});
// ==========================================
// ১. ডেটাবেস কানেকশন (MongoDB)
// ==========================================
mongoose.connect('mongodb://localhost:27017/bangla_invest_site')
  .then(() => console.log('✅ ডেটাবেস সফলভাবে কানেক্ট হয়েছে!'))
  .catch(err => console.log('❌ ডেটাবেস এরর:', err));

// ==========================================
// ২. ডেটাবেস মডেল (User Schema)
// ==========================================
const userSchema = new mongoose.Schema({
    name: { type: String, required: true },
    phone: { type: String, required: true, unique: true },
    depositWallet: { type: Number, default: 0 }, // জমার খাতা
    earningsWallet: { type: Number, default: 0 }, // আয়ের খাতা (যেখান থেকে টাকা তুলবে)
    activePlan: {
        planName: { type: String, default: null },
        dailyEarn: { type: Number, default: 0 },
        remainingDays: { type: Number, default: 0 }
    }
});

const User = mongoose.model('User', userSchema);

// ==========================================
// ৩. এপিআই রাউটস (API Routes)
// ==========================================

// ৩.১ নতুন ইউজার তৈরি (Registration)
app.post('/api/register', async (req, res) => {
    try {
        const { name, phone } = req.body;
        const newUser = new User({ name, phone });
        await newUser.save();
        res.status(201).json({ message: "অ্যাকাউন্ট সফলভাবে তৈরি হয়েছে!", user: newUser });
    } catch (error) {
        res.status(400).json({ message: "অ্যাকাউন্ট তৈরি করতে সমস্যা হয়েছে। ফোন নম্বরটি আগেই ব্যবহৃত হতে পারে।" });
    }
});

// ৩.২ টাকা জমা করা (Manual Deposit/Admin Approval Logic)
app.post('/api/deposit', async (req, res) => {
    try {
        const { phone, amount } = req.body;
        const user = await User.findOne({ phone });
        
        if (!user) return res.status(404).json({ message: "ইউজার পাওয়া যায়নি।" });

        user.depositWallet += amount;
        await user.save();
        res.json({ message: `${amount} টাকা সফলভাবে ডিপোজিট খাতায় যোগ হয়েছে।`, balance: user.depositWallet });
    } catch (error) {
        res.status(500).json({ message: "সার্ভার এরর।" });
    }
});

// ৩.৩ প্ল্যান কেনা (Buy Investment Plan)
app.post('/api/buy-plan', async (req, res) => {
    try {
        const { phone, planName, planPrice, dailyEarn, planDays } = req.body;
        const user = await User.findOne({ phone });

        if (!user) return res.status(404).json({ message: "ইউজার পাওয়া যায়নি।" });

        // ব্যালেন্স চেক করা
        if (user.depositWallet >= planPrice) {
            user.depositWallet -= planPrice; // ব্যালেন্স থেকে প্ল্যানের দাম কাটা হলো
            
            // প্ল্যান এক্টিভ করা হলো
            user.activePlan = {
                planName: planName,
                dailyEarn: dailyEarn,
                remainingDays: planDays
            };

            await user.save();
            res.json({ message: `অভিনন্দন! আপনি সফলভাবে '${planName}' কিনেছেন।` });
        } else {
            res.status(400).json({ message: "আপনার ডিপোজিট ব্যালেন্স পর্যাপ্ত নয়। দয়া করে রিচার্জ করুন।" });
        }
    } catch (error) {
        res.status(500).json({ message: "সার্ভার এরর।" });
    }
});

// ৩.৪ ড্যাশবোর্ড চেক করা (Check User Status)
app.get('/api/dashboard/:phone', async (req, res) => {
    try {
        const user = await User.findOne({ phone: req.params.phone });
        if (!user) return res.status(404).json({ message: "ইউজার পাওয়া যায়নি।" });
        res.json(user);
    } catch (error) {
        res.status(500).json({ message: "সার্ভার এরর।" });
    }
});

// ==========================================
// ৪. অটোমেশন সিস্টেম (Daily Earning Cron Job)
// ==========================================
// প্রতিদিন রাত ১২ টায় (0 0 * * *) এই স্ক্রিপ্ট চলবে। 
// টেস্টিং এর জন্য আপনি '0 0 * * *' এর জায়গায় '* * * * *' দিতে পারেন (তাহলে প্রতি মিনিটে টাকা যোগ হবে)।
cron.schedule('0 0 * * *', async () => {
    console.log('⏳ প্রতিদিনের আয় বন্টন শুরু হয়েছে...');
    
    try {
        // যাদের প্ল্যানের মেয়াদ অন্তত ১ দিন বাকি আছে, শুধু তাদের খুঁজে বের করা
        const activeUsers = await User.find({ "activePlan.remainingDays": { $gt: 0 } });

        for (let user of activeUsers) {
            // ইউজারের আয়ের খাতায় নির্দিষ্ট টাকা যোগ করা
            user.earningsWallet += user.activePlan.dailyEarn;
            // প্ল্যানের মেয়াদ ১ দিন কমিয়ে দেওয়া
            user.activePlan.remainingDays -= 1;
            
            // যদি মেয়াদ শেষ হয়ে যায়, প্ল্যান মুছে ফেলা
            if (user.activePlan.remainingDays === 0) {
                user.activePlan = { planName: null, dailyEarn: 0, remainingDays: 0 };
            }

            await user.save();
        }
        
        console.log(`✅ সফলভাবে ${activeUsers.length} জন ইউজারের অ্যাকাউন্টে টাকা যোগ করা হয়েছে!`);
    } catch (error) {
        console.error('❌ টাকা বন্টনে সমস্যা হয়েছে:', error);
    }
});

// ==========================================
// ৫. সার্ভার চালু করা
// ==========================================
const PORT = 3000;
app.listen(PORT, () => {
    console.log(`🚀 সার্ভার চালু হয়েছে: http://localhost:${PORT}`);
});