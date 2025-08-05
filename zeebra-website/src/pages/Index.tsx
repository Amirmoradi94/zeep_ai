import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ArrowRight, Zap, Shield, ShoppingBag, Search } from "lucide-react";
import Particles from '@/components/Particles';
import Bee from '@/components/Bee';

const benefitCategories = [
  {
    title: "Fashion Enthusiasts",
    desc: "Discover and shop the latest fashion trends instantly from your favorite influencers",
    price: "$89.99",
    store: "Zara • In Stock",
    gradient: "from-pink-400 to-rose-400",
  },
  {
    title: "Beauty Lovers", 
    desc: "Find makeup, skincare, and beauty products featured by influencers and beauty gurus",
    price: "$64.99",
    store: "Sephora • 2 left",
    gradient: "from-purple-400 to-pink-400",
  },
  {
    title: "Tech Lovers",
    desc: "Find and compare the latest gadgets and tech products featured in Instagram content", 
    price: "$299.99",
    store: "Best Buy • In Stock",
    gradient: "from-blue-400 to-cyan-400",
  },
  {
    title: "Home Decorators",
    desc: "Transform your space with furniture and decor items spotted in lifestyle posts",
    price: "$149.99", 
    store: "IKEA • Available",
    gradient: "from-green-400 to-teal-400",
  },
  {
    title: "Trend Hunters",
    desc: "Stay ahead of the curve by discovering unique and trending products before they go mainstream",
    price: "$79.99",
    store: "Urban Outfitters • Limited",
    gradient: "from-orange-400 to-yellow-400",
  }
];

const Navigation = () => (
  <header className="w-full bg-[#18192a] shadow-md border-b border-[#23244a] pb-2 relative">
    <div className="flex flex-row items-center max-w-7xl mx-auto pt-4 px-6 relative">
      <div className="text-4xl font-extrabold bg-gradient-to-r from-cyan-400 via-blue-400 to-purple-500 bg-clip-text text-transparent drop-shadow-[0_0_16px_rgba(99,102,241,0.7)]">
        Zeebra
      </div>
      <nav className="absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2">
        <ul className="flex space-x-12 text-lg">
          <li><a href="#how-it-works" className="text-gray-100 hover:text-cyan-400 transition-colors font-semibold">How It Works</a></li>
          <li><a href="#features" className="text-gray-100 hover:text-cyan-400 transition-colors font-semibold">Features</a></li>
          <li><a href="#contact" className="text-gray-100 hover:text-cyan-400 transition-colors font-semibold">Contact</a></li>
        </ul>
      </nav>
    </div>
  </header>
);

const HeroSection = () => (
  <section className="relative pt-20 pb-32 px-6 min-h-screen flex items-center">
    <div className="max-w-7xl mx-auto w-full">
      <div className="grid lg:grid-cols-2 gap-16 items-center">
        <div className="text-left space-y-8 animate-slide-up">
          <div className="inline-flex items-center px-4 py-2 rounded-full bg-gradient-to-r from-cyan-500/20 to-purple-600/20 border border-cyan-400/30 glass-morphism animate-glow">
            <svg className="w-4 h-4 mr-2 text-cyan-300 animate-spin" fill="none" viewBox="0 0 24 24">
              <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
            </svg>
            <span className="text-cyan-300 font-medium text-sm">AI-Powered Shopping Assistant</span>
          </div>

          <div className="space-y-4">
            <h1 className="text-5xl md:text-6xl lg:text-7xl font-black leading-tight">
              <span className="bg-gradient-to-r from-cyan-300 via-blue-400 to-purple-500 bg-clip-text text-transparent text-shadow animate-fade-in">
                Zeebra
              </span>
            </h1>
            
            <div className="text-2xl md:text-3xl lg:text-4xl font-bold text-white/90 leading-relaxed">
              Turn Instagram into your
              <span className="bg-gradient-to-r from-pink-400 to-orange-400 bg-clip-text text-transparent"> personal shopper</span>
            </div>
          </div>

          <p className="text-lg md:text-xl text-gray-300 leading-relaxed max-w-lg">
            Share any Instagram reel and instantly find where to buy exactly what you see. BeeBlue identifies products in seconds and shows you the best deals across the web.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 pt-4">
            <button className="group relative bg-gradient-to-r from-cyan-400 to-purple-600 hover:from-cyan-500 hover:to-purple-700 text-white font-semibold text-lg px-8 py-4 rounded-full shadow-lg shadow-cyan-500/25 transform hover:scale-105 transition-all duration-200 overflow-hidden">
              <span className="relative z-10 flex items-center justify-center">
                Start Shopping Now
                <svg className="ml-2 w-5 h-5 group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7l5 5m0 0l-5 5m5-5H6"/>
                </svg>
              </span>
              <div className="absolute inset-0 bg-gradient-to-r from-purple-600 to-cyan-400 opacity-0 group-hover:opacity-100 transition-opacity duration-200"></div>
            </button>
          </div>
        </div>

        <div className="relative animate-float">
          <div className="relative bg-gradient-to-br from-cyan-500/10 to-purple-600/10 rounded-3xl p-8 glass-morphism border border-cyan-400/20 shadow-2xl">
            <div className="bg-gray-900/80 rounded-3xl p-1 border border-gray-600/30 max-w-sm mx-auto shadow-2xl">
              <div className="bg-gradient-to-b from-gray-900 to-black rounded-3xl overflow-hidden border border-gray-700/50">
                <div className="h-6 bg-black rounded-t-3xl relative">
                  <div className="absolute top-2 left-1/2 transform -translate-x-1/2 w-16 h-1 bg-gray-700 rounded-full"></div>
                </div>

                <div className="flex items-center justify-between p-4 bg-gradient-to-r from-gray-800/50 to-gray-900/50 border-b border-gray-700/30">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 bg-gradient-to-br from-cyan-400 to-purple-500 rounded-full flex items-center justify-center">
                      <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
                      </svg>
                    </div>
                    <div>
                      <span className="text-white font-semibold text-sm">Zeebra AI</span>
                      <div className="flex items-center space-x-1">
                        <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                        <span className="text-green-400 text-xs">Online</span>
                      </div>
                    </div>
                  </div>
                  <button className="text-gray-400 hover:text-white">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"/>
                    </svg>
                  </button>
                </div>

                <div className="p-4 space-y-4 h-96 overflow-hidden bg-gradient-to-b from-gray-900/50 to-black/50" id="chatContainer">
                  <div className="flex justify-end animate-slide-up">
                    <div className="bg-gradient-to-r from-blue-600 to-blue-700 rounded-2xl rounded-br-md p-4 max-w-xs shadow-lg">
                      <div className="bg-black/40 rounded-xl p-3 mb-3 border border-pink-500/20">
                        <div className="flex items-center space-x-2 mb-2">
                          <svg className="w-4 h-4 text-pink-400" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                          </svg>
                          <span className="text-pink-300 text-xs font-medium">Instagram Post</span>
                        </div>
                        <div className="w-full h-24 bg-gradient-to-br from-pink-500/30 to-purple-500/30 rounded-lg border border-pink-400/20 flex items-center justify-center">
                          <svg className="w-8 h-8 text-pink-400/60" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                          </svg>
                        </div>
                      </div>
                      <p className="text-white text-sm font-medium">Help me find this outfit! 🔍</p>
                    </div>
                  </div>

                  <div className="flex justify-start animate-slide-up" style={{ animationDelay: '0.5s' }}>
                    <div className="bg-gradient-to-r from-gray-700 to-gray-800 rounded-2xl rounded-bl-md p-4 max-w-xs shadow-lg border border-cyan-400/20">
                      <div className="flex items-center space-x-2 mb-3">
                        <div className="w-6 h-6 bg-gradient-to-br from-cyan-400 to-purple-500 rounded-full flex items-center justify-center">
                          <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
                          </svg>
                        </div>
                        <span className="text-cyan-300 text-xs font-semibold">Zeebra AI</span>
                        <div className="flex space-x-1">
                          <div className="w-1 h-1 bg-cyan-400 rounded-full animate-bounce"></div>
                          <div className="w-1 h-1 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                          <div className="w-1 h-1 bg-cyan-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                        </div>
                      </div>
                      <p className="text-white text-sm mb-3 font-medium">Perfect! I found 3 exact matches:</p>
                      
                      <div className="space-y-3">
                        <div className="bg-gradient-to-r from-green-500/20 to-emerald-500/20 rounded-lg p-3 border border-green-400/30 cursor-pointer hover:scale-105 transition-transform">
                          <div className="flex items-center space-x-3">
                            <div className="w-10 h-10 bg-gradient-to-br from-green-400 to-emerald-500 rounded-lg flex items-center justify-center">
                              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z"/>
                              </svg>
                            </div>
                            <div className="flex-1">
                              <div className="text-green-300 font-bold text-sm">$89.99</div>
                              <div className="text-gray-300 text-xs">Zara • In Stock</div>
                              <div className="flex items-center space-x-1 mt-1">
                                <span className="text-yellow-400 text-xs">★★★★★</span>
                                <span className="text-gray-400 text-xs">(124)</span>
                              </div>
                            </div>
                            <div className="text-green-400">
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"/>
                              </svg>
                            </div>
                          </div>
                        </div>
                        
                        <div className="bg-gradient-to-r from-blue-500/20 to-cyan-500/20 rounded-lg p-3 border border-blue-400/30 cursor-pointer hover:scale-105 transition-transform">
                          <div className="flex items-center space-x-3">
                            <div className="w-10 h-10 bg-gradient-to-br from-blue-400 to-cyan-500 rounded-lg flex items-center justify-center">
                              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z"/>
                              </svg>
                            </div>
                            <div className="flex-1">
                              <div className="text-blue-300 font-bold text-sm">$64.99</div>
                              <div className="text-gray-300 text-xs">H&M • 2 left</div>
                              <div className="flex items-center space-x-1 mt-1">
                                <span className="text-yellow-400 text-xs">★★★★☆</span>
                                <span className="text-gray-400 text-xs">(89)</span>
                              </div>
                            </div>
                            <div className="text-blue-400">
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"/>
                              </svg>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="p-4 bg-gradient-to-r from-gray-800/80 to-gray-900/80 border-t border-gray-700/30">
                  <div className="relative">
                    <input 
                      type="text" 
                      placeholder="Paste Instagram link or upload image..." 
                      className="w-full bg-gray-700/50 text-gray-300 text-sm rounded-full px-4 py-3 pr-12 outline-none border border-gray-600/30 focus:border-cyan-400/50 focus:bg-gray-700/70 transition-all glass-morphism"
                      disabled
                    />
                    <button className="absolute right-2 top-1/2 transform -translate-y-1/2 bg-gradient-to-r from-cyan-400 to-purple-500 rounded-full p-2 hover:scale-110 transition-transform">
                      <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
);

const FeaturesSection = () => (
  <section className="py-20 px-6 bg-black/10 backdrop-blur-sm">
    <div className="max-w-7xl mx-auto">
      <div className="text-center mb-16">
        <h2 className="text-4xl md:text-6xl font-bold mb-6">
          <span className="bg-gradient-to-r from-cyan-300 to-purple-400 bg-clip-text text-transparent">
            What is Zeebra?
          </span>
        </h2>
        <p className="text-xl text-gray-300 max-w-3xl mx-auto">
          Zeebra is an intelligent AI shopping assistant that bridges the gap between Instagram content and shopping, 
          making product discovery effortless and instant.
        </p>
      </div>

      <div className="grid md:grid-cols-3 gap-8">
        <Card className="bg-gradient-to-br from-blue-900/30 to-cyan-900/30 border-cyan-400/20 hover:border-cyan-400/40 transition-all duration-300 backdrop-blur-sm">
          <CardContent className="p-8 text-center">
            <Search className="w-12 h-12 text-cyan-400 mx-auto mb-4" />
            <h3 className="text-xl font-bold text-white mb-4">Instant Recognition</h3>
            <p className="text-gray-300">
              Our AI instantly identifies products in any Instagram content with 99% accuracy
            </p>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-purple-900/30 to-blue-900/30 border-purple-400/20 hover:border-purple-400/40 transition-all duration-300 backdrop-blur-sm">
          <CardContent className="p-8 text-center">
            <Zap className="w-12 h-12 text-purple-400 mx-auto mb-4" />
            <h3 className="text-xl font-bold text-white mb-4">Lightning Fast</h3>
            <p className="text-gray-300">
              Get product information and purchase links in seconds, not minutes
            </p>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-green-900/30 to-blue-900/30 border-green-400/20 hover:border-green-400/40 transition-all duration-300 backdrop-blur-sm">
          <CardContent className="p-8 text-center">
            <Shield className="w-12 h-12 text-green-400 mx-auto mb-4" />
            <h3 className="text-xl font-bold text-white mb-4">Secure & Private</h3>
            <p className="text-gray-300">
              Your data is encrypted and protected with enterprise-grade security
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  </section>
);

const BenefitsSection = () => (
  <section id="benefits" className="py-20 px-6 bg-black/10 backdrop-blur-sm">
    <div className="max-w-7xl mx-auto">
      <div className="text-center mb-16">
        <h2 className="text-4xl md:text-6xl font-bold mb-6">
          <span className="bg-gradient-to-r from-yellow-300 to-orange-400 bg-clip-text text-transparent">
            Why Use Zeebra AI?
          </span>
        </h2>
        <p className="text-xl text-gray-300 max-w-3xl mx-auto">
          Experience the future of social commerce with unmatched convenience and accuracy
        </p>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[
          { icon: Zap, title: "Save Time", desc: "No more endless searching for products you saw on Instagram" },
          { icon: Search, title: "Find Anything", desc: "Identify products from clothing to gadgets with 99% accuracy" },
          { icon: ShoppingBag, title: "Best Prices", desc: "Compare prices across multiple retailers instantly" },
          { icon: Shield, title: "Safe Shopping", desc: "Verified retailers and secure purchase links only" }
        ].map((item, index) => (
          <Card key={index} className="bg-gradient-to-br from-gray-900/30 to-black/30 border-gray-600/20 hover:border-cyan-400/40 transition-all duration-300 hover:scale-105 backdrop-blur-sm">
            <CardContent className="p-6 text-center">
              <item.icon className="w-10 h-10 text-cyan-400 mx-auto mb-4" />
              <h3 className="text-lg font-bold text-white mb-2">{item.title}</h3>
              <p className="text-gray-400 text-sm">{item.desc}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  </section>
);

const WhoCanBenefitCarousel = () => {
  const [currentSlide, setCurrentSlide] = useState(0);

  const nextSlide = () => {
    setCurrentSlide((prev) => (prev + 1) % benefitCategories.length);
  };

  const prevSlide = () => {
    setCurrentSlide((prev) => (prev - 1 + benefitCategories.length) % benefitCategories.length);
  };

  const getRotationAngle = (index: number) => {
    const angle = ((index - currentSlide) * 72) % 360; // 72 degrees between each frame (360/5)
    return angle;
  };

  const getZIndex = (index: number) => {
    const distance = Math.abs(index - currentSlide);
    return distance === 0 ? 50 : 50 - distance;
  };

  return (
    <section className="py-20 px-6">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="text-4xl md:text-6xl font-bold mb-6">
            <span className="bg-gradient-to-r from-purple-300 to-pink-400 bg-clip-text text-transparent">
              Who Can Benefit?
            </span>
          </h2>
          <p className="text-xl text-gray-300 max-w-3xl mx-auto mb-8">
            Zeebra is designed for everyone who loves discovering and shopping for products on Instagram
          </p>

          <p className="text-gray-300 mb-8">Hang tight while I hunt for the best product matches! 🛍️</p>
        </div>

        <div className="relative">
          {/* 3D Carousel Container */}
          <div className="relative h-[600px] flex items-center justify-center" style={{ perspective: '1000px' }}>
            <div className="relative w-full h-full" style={{ transformStyle: 'preserve-3d' }}>
              {benefitCategories.map((category, index) => {
                const rotation = getRotationAngle(index);
                const isCenter = index === currentSlide;
                
                return (
                  <div
                    key={index}
                    className="absolute left-1/2 top-1/2 transition-all duration-700 ease-out"
                    style={{
                      transform: `translate(-50%, -50%) rotateY(${rotation}deg) translateZ(280px) ${isCenter ? 'scale(1.1)' : 'scale(0.8)'}`,
                      zIndex: getZIndex(index),
                      opacity: Math.abs(rotation) > 90 && Math.abs(rotation) < 270 ? 0.3 : 1,
                      transformStyle: 'preserve-3d'
                    }}
                  >
                    {/* Smartphone Frame */}
                    <div className="relative w-80 h-[520px]">
                      {/* iPhone 16 Bezel */}
                      <div className="absolute inset-0 bg-gradient-to-b from-gray-800 to-gray-900 rounded-[3rem] shadow-2xl border-4 border-gray-700">
                        {/* Dynamic Island (pill notch) */}
                        <div className="absolute top-6 left-1/2 transform -translate-x-1/2 w-28 h-6 bg-black/80 rounded-full shadow-md"></div>
                        {/* Empty Screen */}
                        <div className="absolute top-10 left-4 right-4 bottom-8 bg-black rounded-[2.5rem] overflow-hidden flex items-center justify-center">
                          {/* Empty for now */}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
            
            {/* Navigation Buttons */}
            <button
              onClick={prevSlide}
              className="absolute left-8 top-1/2 transform -translate-y-1/2 z-50 bg-gray-800/80 hover:bg-gray-700/80 border border-gray-600/30 text-white w-12 h-12 rounded-full flex items-center justify-center transition-all duration-200"
            >
              <ArrowRight className="w-5 h-5 rotate-180" />
            </button>
            
            <button
              onClick={nextSlide}
              className="absolute right-8 top-1/2 transform -translate-y-1/2 z-50 bg-gray-800/80 hover:bg-gray-700/80 border border-gray-600/30 text-white w-12 h-12 rounded-full flex items-center justify-center transition-all duration-200"
            >
              <ArrowRight className="w-5 h-5" />
            </button>
          </div>

          {/* Slide Indicators */}
          <div className="flex justify-center space-x-2 mt-8">
            {benefitCategories.map((_, index) => (
              <button
                key={index}
                onClick={() => setCurrentSlide(index)}
                className={`w-3 h-3 rounded-full transition-all duration-200 ${
                  index === currentSlide ? 'bg-cyan-400' : 'bg-gray-600'
                }`}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};

const ReadyToTransformSection = () => (
  <section className="py-20 px-6 bg-gradient-to-r from-cyan-900/30 to-purple-900/30 backdrop-blur-sm">
    <div className="max-w-4xl mx-auto text-center">
      <h2 className="text-4xl md:text-6xl font-bold mb-6">
        <span className="bg-gradient-to-r from-cyan-300 to-purple-400 bg-clip-text text-transparent">
          Ready to Transform Your Shopping?
        </span>
      </h2>
      <p className="text-xl text-gray-300 mb-8">
        Join thousands of users who have revolutionized their Instagram shopping experience with Zeebra
      </p>
      <Button size="lg" className="bg-gradient-to-r from-cyan-400 to-purple-600 hover:from-cyan-500 hover:to-purple-700 text-lg px-12 py-6 shadow-lg shadow-cyan-500/25">
        Start Shopping Smarter Today
        <ArrowRight className="ml-2 w-5 h-5" />
      </Button>
    </div>
  </section>
);

const Footer = () => (
  <footer className="py-12 px-6 bg-black/30 border-t border-gray-800 backdrop-blur-sm">
    <div className="max-w-7xl mx-auto text-center">
      <div className="text-3xl font-bold bg-gradient-to-r from-cyan-300 to-purple-400 bg-clip-text text-transparent mb-4">
        Zeebra
      </div>
      <p className="text-gray-400 mb-6">The future of Instagram shopping is here</p>
      <div className="flex justify-center space-x-6 text-gray-400">
        <a href="#" className="hover:text-cyan-400 transition-colors">Privacy</a>
        <a href="#" className="hover:text-cyan-400 transition-colors">Terms</a>
        <a href="#" className="hover:text-cyan-400 transition-colors">Contact</a>
      </div>
    </div>
  </footer>
);

const Index = () => {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    setIsVisible(true);
  }, []);

  return (
    <>
      <div className="min-h-screen starry-bg" style={{ position: 'relative' }}>
        <Bee />
        <Particles />

        <Navigation />
        <HeroSection />
        <FeaturesSection />
        <BenefitsSection />
        <WhoCanBenefitCarousel />
        <ReadyToTransformSection />
        <Footer />
      </div>
    </>
  );
};

export default Index;
